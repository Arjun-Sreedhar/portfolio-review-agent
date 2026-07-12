from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Any


def _portfolio_total(holdings: list[dict[str, Any]]) -> float:
    return sum(max(float(holding.get("market_value", 0.0)), 0.0) for holding in holdings)


def _bucket_percentages(values: dict[str, float], total: float) -> dict[str, float]:
    if total <= 0:
        return {key: 0.0 for key in values}
    return {key: round((value / total) * 100.0, 2) for key, value in values.items()}


def _risk_label(top_weight: float, hhi: float) -> str:
    if top_weight >= 25.0 or hhi >= 0.22:
        return "High"
    if top_weight >= 15.0 or hhi >= 0.12:
        return "Moderate"
    return "Low"


def analyze_portfolio(holdings: list[dict[str, Any]], client_profile: dict[str, Any]) -> dict[str, Any]:
    total_value = _portfolio_total(holdings)
    asset_class_values: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    ticker_weights: list[tuple[str, float, float]] = []

    weighted_expense_ratio = 0.0
    for holding in holdings:
        market_value = max(float(holding.get("market_value", 0.0)), 0.0)
        if total_value > 0:
            weight = market_value / total_value
        else:
            weight = 0.0
        ticker = str(holding.get("ticker", "Unknown"))
        asset_class = str(holding.get("asset_class", "Unknown"))
        sector = str(holding.get("sector", "Unknown"))
        expense_ratio = float(holding.get("expense_ratio", 0.0))

        asset_class_values[asset_class] += market_value
        sector_values[sector] += market_value
        ticker_weights.append((ticker, market_value, weight))
        weighted_expense_ratio += expense_ratio * weight

    asset_allocation = _bucket_percentages(dict(asset_class_values), total_value)
    sector_exposure = _bucket_percentages(dict(sector_values), total_value)
    ticker_weights.sort(key=lambda item: item[1], reverse=True)

    top_holding_weight = round(ticker_weights[0][2] * 100.0, 2) if ticker_weights else 0.0
    top_three_weight = round(sum(weight for _, _, weight in ticker_weights[:3]) * 100.0, 2)
    hhi = round(sum((weight * 100.0) ** 2 for _, _, weight in ticker_weights) / 10000.0, 4)
    concentration_risk = _risk_label(top_holding_weight, hhi)
    weighted_expense_ratio_pct = round(weighted_expense_ratio * 100.0, 2)

    risk_tolerance = str(client_profile.get("risk_tolerance") or "Unknown")
    goal = str(client_profile.get("goal") or "General Review")
    horizon = str(client_profile.get("investment_horizon") or "Unknown")
    age = client_profile.get("age")

    recommendations: list[str] = []
    risk_flags: list[str] = []

    if top_holding_weight >= 20.0:
        risk_flags.append(
            f"The largest holding represents {top_holding_weight:.2f}% of the portfolio, creating concentration risk."
        )
        recommendations.append("Trim the largest position or offset it with broader diversification.")

    tech_exposure = sector_exposure.get("Technology", 0.0)
    if tech_exposure >= 25.0:
        risk_flags.append(f"Technology exposure is elevated at {tech_exposure:.2f}%.")
        recommendations.append("Reduce technology concentration if the client wants a smoother return profile.")

    if weighted_expense_ratio_pct >= 0.75:
        risk_flags.append(
            f"Weighted expense ratio is {weighted_expense_ratio_pct:.2f}%, which is high for a long-term portfolio."
        )
        recommendations.append("Review high-fee funds and replace them with lower-cost alternatives where suitable.")

    if risk_tolerance.lower() in {"moderate", "conservative"} and asset_allocation.get("Equity", 0.0) >= 70.0:
        risk_flags.append(
            f"Equity allocation is {asset_allocation.get('Equity', 0.0):.2f}% for a {risk_tolerance.lower()} investor."
        )
        recommendations.append("Consider adding bonds or cash-like assets to better align with the stated risk tolerance.")

    if not recommendations:
        recommendations.append("The portfolio is broadly aligned with the available profile data.")

    if not risk_flags:
        risk_flags.append("No material concentration or fee issues were detected from the uploaded holdings.")

    return {
        "total_market_value": round(total_value, 2),
        "asset_allocation": asset_allocation,
        "sector_exposure": sector_exposure,
        "concentration_risk": concentration_risk,
        "top_holding": ticker_weights[0][0] if ticker_weights else None,
        "top_holding_weight": top_holding_weight,
        "top_three_weight": top_three_weight,
        "hhi": hhi,
        "expense_ratio": weighted_expense_ratio_pct,
        "risk_tolerance": risk_tolerance,
        "investment_goal": goal,
        "investment_horizon": horizon,
        "age": age,
        "risk_flags": risk_flags,
        "recommended_actions": recommendations,
    }
