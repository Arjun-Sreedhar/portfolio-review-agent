from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _build_prompt(analysis: dict[str, Any], profile: dict[str, Any], parser_result: dict[str, Any], profile_result: dict[str, Any]) -> str:
    payload = {
        "analysis": analysis,
        "client_profile": profile,
        "parser_result": {
            "parse_status": parser_result.get("parse_status"),
            "warnings": parser_result.get("warnings", []),
        },
        "profile_result": {
            "parse_status": profile_result.get("parse_status"),
            "warnings": profile_result.get("warnings", []),
        },
    }
    return (
        "You are preparing an advisor-ready portfolio review. "
        "Use only the supplied structured data. Do not calculate new metrics. "
        "Write concise, professional copy for a wealth advisor before a client meeting. "
        "Return ONLY valid JSON. Do not wrap it in markdown. Do not include explanations. "
        "Return JSON with keys: title, summary, allocation, risks, recommendations, talking_points, structured_json.\n\n"
        + json.dumps(payload, indent=2)
    )


def _fallback_review(
    analysis: dict[str, Any],
    profile: dict[str, Any],
    parser_result: dict[str, Any],
    profile_result: dict[str, Any],
) -> dict[str, Any]:
    summary = (
        f"The portfolio for a {profile.get('risk_tolerance') or 'general'} investor with goal "
        f"{profile.get('goal') or 'General Review'} shows {analysis['concentration_risk'].lower()} concentration risk."
    )
    allocation_lines = [f"{name}: {value:.2f}%" for name, value in analysis["asset_allocation"].items()]
    risk_lines = list(analysis["risk_flags"])
    if parser_result.get("warnings"):
        risk_lines.extend(parser_result["warnings"])
    if profile_result.get("warnings"):
        risk_lines.extend(profile_result["warnings"])

    recommendations = list(analysis["recommended_actions"])
    if profile_result.get("warnings"):
        recommendations.insert(0, "Recommendations are based on incomplete client information.")

    return {
        "title": "Portfolio Review",
        "summary": summary,
        "allocation": allocation_lines,
        "risks": risk_lines,
        "recommendations": recommendations,
        "talking_points": [
            f"Total market value reviewed: ₹{analysis['total_market_value']:,.2f}",
            f"Top holding: {analysis['top_holding'] or 'N/A'} at {analysis['top_holding_weight']:.2f}%",
            f"Weighted expense ratio: {analysis['expense_ratio']:.2f}%",
        ],
        "structured_json": {
            "summary": summary,
            "allocation": analysis["asset_allocation"],
            "risk_flags": analysis["risk_flags"],
            "recommendations": analysis["recommended_actions"],
        },
    }


def _call_openai(prompt: str) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except Exception:
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
        )
        text = getattr(response, "output_text", "") or ""
        if not text.strip():
            return None
        return json.loads(text)
    except Exception:
        return None


def generate_portfolio_review(
    analysis: dict[str, Any],
    profile: dict[str, Any],
    parser_result: dict[str, Any],
    profile_result: dict[str, Any],
) -> dict[str, Any]:
    prompt = _build_prompt(analysis, profile, parser_result, profile_result)
    generated = _call_openai(prompt)
    if generated is None:
        return _fallback_review(analysis, profile, parser_result, profile_result)

    return {
        "title": generated.get("title", "Portfolio Review"),
        "summary": generated.get("summary", ""),
        "allocation": generated.get("allocation", []),
        "risks": generated.get("risks", []),
        "recommendations": generated.get("recommendations", []),
        "talking_points": generated.get("talking_points", []),
        "structured_json": generated.get(
            "structured_json",
            {
                "summary": generated.get("summary", ""),
                "allocation": analysis["asset_allocation"],
                "risk_flags": analysis["risk_flags"],
                "recommendations": analysis["recommended_actions"],
            },
        ),
    }
