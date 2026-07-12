from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, TypedDict

from dotenv import load_dotenv

from agents import Agent, RunContextWrapper, Runner, function_tool
from agents.agent import ModelSettings

from tools.portfolio_analysis import analyze_portfolio
from tools.portfolio_parser import parse_client_profile, parse_portfolio
from tools.portfolio_review_generator import generate_portfolio_review

load_dotenv()


class ReviewContext(TypedDict):
    portfolio_name: str
    portfolio_bytes: bytes
    client_profile_name: str
    client_profile_bytes: bytes
    parser_result: dict[str, Any] | None
    profile_result: dict[str, Any] | None
    analysis: dict[str, Any] | None
    decision_log: list[str]
    workflow_note: str


@dataclass
class AgentResult:
    status: str
    report: dict[str, Any] | None = None
    structured_json: dict[str, Any] | None = None
    parser_result: dict[str, Any] | None = None
    profile_result: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    decision_log: list[str] | None = None
    error: str | None = None


@function_tool
async def parse_portfolio_tool(
    ctx: RunContextWrapper[ReviewContext],
) -> dict[str, Any]:
    """Parse the uploaded portfolio file into structured holdings and warnings."""
    result = parse_portfolio(ctx.context["portfolio_name"], ctx.context["portfolio_bytes"])
    ctx.context["parser_result"] = result
    return result


@function_tool
async def parse_client_profile_tool(
    ctx: RunContextWrapper[ReviewContext],
) -> dict[str, Any]:
    """Parse the uploaded client profile JSON into structured context."""
    result = parse_client_profile(
        ctx.context["client_profile_name"],
        ctx.context["client_profile_bytes"],
    )
    ctx.context["profile_result"] = result
    return result


@function_tool
async def analyze_portfolio_tool(
    ctx: RunContextWrapper[ReviewContext],
) -> dict[str, Any]:
    """Run deterministic portfolio calculations using the parsed holdings and client profile."""
    parser_result = ctx.context.get("parser_result")
    profile_result = ctx.context.get("profile_result")
    if not parser_result or not profile_result:
        raise ValueError("Parser and profile results are required before analysis.")

    profile = profile_result["profile"]
    result = analyze_portfolio(parser_result["holdings"], profile)
    ctx.context["analysis"] = result
    return result


@function_tool
async def generate_portfolio_review_tool(
    ctx: RunContextWrapper[ReviewContext],
) -> dict[str, Any]:
    """Generate the advisor-ready review from deterministic analysis and client context."""
    parser_result = ctx.context.get("parser_result")
    profile_result = ctx.context.get("profile_result")
    analysis = ctx.context.get("analysis")
    if not parser_result or not profile_result or not analysis:
        raise ValueError("Parser, profile, and analysis results are required before review generation.")

    ctx.context["decision_log"].append(
        f"Generating review after analysis showed {analysis['concentration_risk']} concentration risk."
    )
    report = generate_portfolio_review(
        analysis=analysis,
        profile=profile_result["profile"],
        parser_result=parser_result,
        profile_result=profile_result,
    )
    return report


portfolio_review_agent = Agent[ReviewContext](
    name="Portfolio Review Agent",
    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    instructions=(
        "You are a portfolio review orchestrator for wealth advisors. "
        "Always parse the portfolio and client profile before analysis. "
        "After each parse, reason over the structured parse status and warnings. "
        "If the portfolio parse is failed, stop and return the parsing issue. "
        "If the portfolio parse is partial, decide whether to continue based on the severity of the warnings and whether the remaining holdings are usable. "
        "If required client information is missing, surface the missing fields and continue only if the profile is still sufficient for a review. "
        "After analysis, decide whether the final review should be concise or more detailed based on concentration risk and profile completeness. "
        "Call the review generator once, then package the final report and structured JSON yourself. "
        "Do not give investment advice directly to the client; this output is for the advisor."
    ),
    tools=[
        parse_portfolio_tool,
        parse_client_profile_tool,
        analyze_portfolio_tool,
        generate_portfolio_review_tool,
    ],
    model_settings=ModelSettings(tool_choice="required"),
)


class PortfolioReviewAgent:
    @staticmethod
    def _finalize_sdk_output(parsed: dict[str, Any], decision_log_fallback: list[str]) -> dict[str, Any]:
        """Determine success vs. error from the agent's actual parse_status fields,
        rather than assuming success just because a 'report' key or valid JSON exists.
        Applied consistently whether the SDK returns a dict or a JSON string."""
        parser_result = parsed.get("parser_result")
        profile_result = parsed.get("profile_result")

        parser_status = parser_result.get("parse_status") if isinstance(parser_result, dict) else None
        profile_status = profile_result.get("parse_status") if isinstance(profile_result, dict) else None

        if parser_status == "failure" or profile_status == "failure":
            error_message = None
            if parser_status == "failure" and isinstance(parser_result, dict) and parser_result.get("warnings"):
                error_message = "Portfolio parsing failed: " + "; ".join(parser_result["warnings"])
            elif profile_status == "failure" and isinstance(profile_result, dict) and profile_result.get("warnings"):
                error_message = "Client profile parsing failed: " + "; ".join(profile_result["warnings"])

            parsed["status"] = "error"
            parsed["runtime"] = "openai_agents_sdk"
            parsed["error"] = error_message or "Unable to generate portfolio review because required input could not be parsed."
            parsed.setdefault("decision_log", decision_log_fallback)
            return parsed

        parsed["status"] = "success"
        parsed["runtime"] = "openai_agents_sdk"
        if not parsed.get("workflow_note"):
            parsed["workflow_note"] = "SDK runtime executed successfully."
        return parsed

    def _run_local_fallback(
        self,
        portfolio_name: str,
        portfolio_bytes: bytes,
        client_profile_name: str,
        client_profile_bytes: bytes,
    ) -> dict[str, Any]:
        decision_log = [
            "Received portfolio and client profile files.",
            "OPENAI_API_KEY is not set; using the deterministic fallback workflow.",
            "Parsing portfolio first to obtain structured holdings.",
        ]

        parser_result = parse_portfolio(portfolio_name, portfolio_bytes)
        if parser_result["parse_status"] == "failure":
            return {
                "status": "error",
                "error": "Portfolio parsing failed: " + "; ".join(parser_result["warnings"]),
                "parser_result": parser_result,
                "decision_log": decision_log,
            }

        decision_log.append(f"Portfolio parse completed with status {parser_result['parse_status']}.")
        if parser_result["warnings"]:
            if parser_result["parse_status"] == "partial":
                decision_log.append(
                    "Detected partial parse. Proceeding because the holdings that were extracted remain usable."
                )
            else:
                decision_log.append("Portfolio parser emitted warnings, but the workflow will continue.")

        decision_log.append("Parsing client profile JSON.")
        profile_result = parse_client_profile(client_profile_name, client_profile_bytes)
        if profile_result["parse_status"] == "failure":
            return {
                "status": "error",
                "error": "Client profile parsing failed: " + "; ".join(profile_result["warnings"]),
                "parser_result": parser_result,
                "profile_result": profile_result,
                "decision_log": decision_log,
            }

        profile = profile_result["profile"]
        decision_log.append("Profile parsed successfully.")
        if profile_result["warnings"]:
            decision_log.append("Profile warnings noted and preserved in the report.")

        decision_log.append("Running deterministic portfolio analysis.")
        analysis = analyze_portfolio(parser_result["holdings"], profile)
        decision_log.append(
            f"Detected {analysis['concentration_risk']} concentration risk and weighted expense ratio {analysis['expense_ratio']:.2f}%."
        )

        decision_log.append("Proceeding to review generation with the structured analysis.")
        report = generate_portfolio_review(
            analysis=analysis,
            profile=profile,
            parser_result=parser_result,
            profile_result=profile_result,
        )

        structured_json = {
            "client_profile": profile,
            "parser": {
                "parse_status": parser_result["parse_status"],
                "warnings": parser_result["warnings"],
                "holdings_count": len(parser_result["holdings"]),
            },
            "analysis": analysis,
            "report": report,
        }

        return {
            "status": "success",
            "runtime": "fallback",
            "report": report,
            "structured_json": structured_json,
            "parser_result": parser_result,
            "profile_result": profile_result,
            "analysis": analysis,
            "decision_log": decision_log,
            "workflow_note": "Fallback runtime used because OPENAI_API_KEY is not set.",
        }

    def run(
        self,
        portfolio_name: str,
        portfolio_bytes: bytes,
        client_profile_name: str,
        client_profile_bytes: bytes,
    ) -> dict[str, Any]:

        if not os.getenv("OPENAI_API_KEY"):
            return self._run_local_fallback(
                portfolio_name,
                portfolio_bytes,
                client_profile_name,
                client_profile_bytes,
            )

        context: ReviewContext = {
            "portfolio_name": portfolio_name,
            "portfolio_bytes": portfolio_bytes,
            "client_profile_name": client_profile_name,
            "client_profile_bytes": client_profile_bytes,
            "parser_result": None,
            "profile_result": None,
            "analysis": None,
            "decision_log": [
                "Received portfolio and client profile files.",
                "Starting OpenAI Agents SDK orchestration.",
            ],
            "workflow_note": "",
        }

        result = Runner.run_sync(
            portfolio_review_agent,
            input=(
                "Review the uploaded portfolio and client profile. "
                "Use the tools in order, "
                "reason over parse status and warnings, "
                "decide whether partial input is usable, "
                "run analysis, "
                "call the review generator once, "
                "and then return a JSON object with the report, "
                "structured_json, parser_result, profile_result, "
                "analysis, decision_log, and workflow_note."
            ),
            context=context,
        )

        final_output = result.final_output

        if isinstance(final_output, dict) and final_output.get("report"):
            return self._finalize_sdk_output(final_output, context["decision_log"])

        if isinstance(final_output, str):
            try:
                parsed = json.loads(final_output)
                if isinstance(parsed, dict):
                    return self._finalize_sdk_output(parsed, context["decision_log"])
            except json.JSONDecodeError:
                pass

        return {
            "status": "error",
            "error": "The agent did not return the expected structured payload.",
            "decision_log": context["decision_log"],
        }