from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None


COLUMN_ALIASES = {
    "ticker": "ticker",
    "symbol": "ticker",
    "asset class": "asset_class",
    "asset_class": "asset_class",
    "market value": "market_value",
    "market_value": "market_value",
    "sector": "sector",
    "expense ratio": "expense_ratio",
    "expense_ratio": "expense_ratio",
}


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_number(value: Any) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace("₹", "")
    text = text.replace("$", "")
    text = text.replace(",", "")
    text = text.replace("%", "")
    text = text.replace(" ", "")
    text = text.replace("(", "-")
    text = text.replace(")", "")
    text = text.replace("—", "")
    text = text.replace("-", "-") if text.startswith("-") else text
    try:
        return float(text)
    except ValueError:
        return None


def _parse_percentage(value: Any) -> float | None:
    text = _clean_text(value)
    number = _parse_number(value)
    if number is None:
        return None
    if "%" in text or number > 1:
        return number / 100.0
    return number


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        canonical = COLUMN_ALIASES.get(_clean_text(key).lower(), _clean_text(key).lower())
        normalized[canonical] = value
    return normalized


def _parse_csv(text: str, source_name: str) -> dict[str, Any]:
    warnings: list[str] = []
    holdings: list[dict[str, Any]] = []

    delimiter = ","
    sample = text[:2048]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        if "\t" in sample:
            delimiter = "\t"
        elif ";" in sample and sample.count(";") > sample.count(","):
            delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": [f"{source_name} does not contain a header row."],
            "source_format": "csv",
        }

    required_columns = {"ticker", "asset_class", "market_value", "sector", "expense_ratio"}
    normalized_fields = {
        COLUMN_ALIASES.get(field.strip().lower(), field.strip().lower()) for field in reader.fieldnames
    }
    missing = sorted(required_columns - normalized_fields)
    if missing:
        warnings.append("Missing expected columns: " + ", ".join(missing))

    for index, row in enumerate(reader, start=1):
        normalized = _normalize_row(row)
        ticker = _clean_text(normalized.get("ticker"))
        if not ticker:
            warnings.append(f"Row {index} is missing a ticker and was skipped.")
            continue

        market_value = _parse_number(normalized.get("market_value"))
        if market_value is None:
            warnings.append(f"Row {index} ({ticker}) has an unreadable market value.")
            continue

        holding = {
            "ticker": ticker,
            "asset_class": _clean_text(normalized.get("asset_class")) or "Unknown",
            "market_value": market_value,
            "sector": _clean_text(normalized.get("sector")) or "Unknown",
            "expense_ratio": _parse_percentage(normalized.get("expense_ratio")) or 0.0,
            "raw": normalized,
        }
        holdings.append(holding)

    if not holdings:
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": warnings or ["No usable holdings were found in the CSV file."],
            "source_format": "csv",
        }

    parse_status = "success" if not warnings else "partial"
    return {
        "holdings": holdings,
        "parse_status": parse_status,
        "warnings": warnings,
        "source_format": "csv",
    }


def _parse_pdf(data: bytes, source_name: str) -> dict[str, Any]:
    warnings: list[str] = []
    if PdfReader is None:
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": ["PDF parsing is unavailable because pypdf is not installed."],
            "source_format": "pdf",
        }

    reader = PdfReader(io.BytesIO(data))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not extracted_text.strip():
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": [f"{source_name} did not contain extractable text."],
            "source_format": "pdf",
        }

    rows = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    if not rows:
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": [f"{source_name} did not contain usable table rows."],
            "source_format": "pdf",
        }

    # Best-effort table extraction from text-based PDFs.
    holdings: list[dict[str, Any]] = []
    headers = None
    for line in rows:
        parts = [part.strip() for part in re.split(r"\s{2,}|\s*\|\s*", line) if part.strip()]
        lowered = {part.lower() for part in parts}
        if {"ticker", "asset class", "market value"}.issubset(lowered):
            headers = parts
            continue
        if headers is None:
            continue
        if len(parts) < 4:
            continue
        row = dict(zip(headers, parts))
        normalized = _normalize_row(row)
        ticker = _clean_text(normalized.get("ticker"))
        market_value = _parse_number(normalized.get("market_value"))
        if not ticker or market_value is None:
            continue
        holdings.append(
            {
                "ticker": ticker,
                "asset_class": _clean_text(normalized.get("asset_class")) or "Unknown",
                "market_value": market_value,
                "sector": _clean_text(normalized.get("sector")) or "Unknown",
                "expense_ratio": _parse_percentage(normalized.get("expense_ratio")) or 0.0,
                "raw": normalized,
            }
        )

    if not holdings:
        warnings.append("PDF text was extracted, but no table rows could be normalized.")
        return {
            "holdings": [],
            "parse_status": "failure",
            "warnings": warnings,
            "source_format": "pdf",
        }

    return {
        "holdings": holdings,
        "parse_status": "partial" if warnings else "success",
        "warnings": warnings,
        "source_format": "pdf",
    }


def parse_portfolio(source_name: str, data: bytes) -> dict[str, Any]:
    suffix = Path(source_name).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(data, source_name)
    if suffix in {".csv", ".txt", ""}:
        return _parse_csv(_decode_bytes(data), source_name)
    return {
        "holdings": [],
        "parse_status": "failure",
        "warnings": [f"Unsupported portfolio format: {suffix or 'unknown'}"],
        "source_format": suffix.lstrip("."),
    }


def parse_client_profile(source_name: str, data: bytes) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        profile = json.loads(_decode_bytes(data))
    except json.JSONDecodeError as exc:
        return {
            "profile": {},
            "parse_status": "failure",
            "warnings": [f"{source_name} is not valid JSON: {exc.msg}"],
        }

    if not isinstance(profile, dict):
        return {
            "profile": {},
            "parse_status": "failure",
            "warnings": [f"{source_name} must contain a JSON object."],
        }

    normalized = {
        "risk_tolerance": _clean_text(
            profile.get("risk_tolerance") or profile.get("riskTolerance") or profile.get("risk")
        ),
        "goal": _clean_text(profile.get("goal") or profile.get("investment_goal") or profile.get("investmentGoal")),
        "investment_horizon": _clean_text(
            profile.get("investment_horizon") or profile.get("investmentHorizon") or profile.get("horizon")
        ),
        "age": profile.get("age"),
        "raw": profile,
    }

    if not normalized["risk_tolerance"]:
        warnings.append("Risk tolerance is missing from the client profile.")
    if not normalized["goal"]:
        warnings.append("Investment goal is missing from the client profile.")
    if not normalized["investment_horizon"]:
        warnings.append("Investment horizon is missing from the client profile.")
    if normalized["age"] in (None, ""):
        warnings.append("Age is missing from the client profile.")

    return {
        "profile": normalized,
        "parse_status": "success" if not warnings else "partial",
        "warnings": warnings,
    }
