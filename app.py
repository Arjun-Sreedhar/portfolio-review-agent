from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from agent import PortfolioReviewAgent

APP_DIR = Path(__file__).resolve().parent
SAMPLE_PORTFOLIO = APP_DIR / "sample_data" / "portfolio.csv"
SAMPLE_PROFILE = APP_DIR / "sample_data" / "client_profile.json"

st.set_page_config(
    page_title="Portfolio Review Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        :root {
            --bg: #07111f;
            --panel: rgba(10, 18, 32, 0.78);
            --panel-border: rgba(157, 177, 203, 0.18);
            --text: #edf2f7;
            --muted: #a9b8ca;
            --accent: #66e3c4;
            --accent-2: #8ab4ff;
            --danger: #ff7b8b;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(102, 227, 196, 0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(138, 180, 255, 0.14), transparent 26%),
                linear-gradient(180deg, #08101d 0%, #07111f 48%, #060d18 100%);
            color: var(--text);
        }
        .hero {
            padding: 2rem 2rem 1.25rem 2rem;
            border: 1px solid var(--panel-border);
            border-radius: 28px;
            background: linear-gradient(180deg, rgba(12, 22, 40, 0.82), rgba(8, 14, 25, 0.7));
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
            margin-bottom: 1.25rem;
        }
        .hero h1 {
            margin: 0;
            font-size: 2.4rem;
            letter-spacing: -0.04em;
        }
        .hero p {
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.6;
            max-width: 68rem;
        }
        .card {
            border: 1px solid var(--panel-border);
            border-radius: 22px;
            background: rgba(11, 20, 34, 0.82);
            padding: 1.1rem 1.1rem 0.85rem 1.1rem;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.2);
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--accent);
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .stTextInput > div > div,
        .stTextArea textarea,
        .stFileUploader section {
            border-radius: 16px !important;
        }
        .stButton > button {
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #07111f;
            border: none;
            border-radius: 14px;
            padding: 0.75rem 1.1rem;
            font-weight: 700;
        }
        .stButton > button:hover {
            filter: brightness(1.05);
            border: none;
        }
        .status-box {
            border: 1px solid var(--panel-border);
            border-radius: 18px;
            padding: 1rem 1rem 0.85rem 1rem;
            background: rgba(10, 18, 30, 0.8);
        }
        .status-ok {
            color: var(--accent);
            font-weight: 700;
        }
        .status-warn {
            color: #ffd27a;
            font-weight: 700;
        }
        .status-error {
            color: var(--danger);
            font-weight: 700;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="section-label">Portfolio Review Agent</div>
        <h1>Advisor-ready portfolio review in one click.</h1>
        <p>
            Upload a portfolio and client profile, then let the agent decide what needs parsing,
            what can be analyzed deterministically, and when to hand structured context to GPT
            for the final advisory narrative.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


def load_sample(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_list_or_text(value, empty_message: str = "Nothing to show.") -> None:
    """Render a field that should be a list of strings, but defensively handle
    the agent occasionally returning a single string or empty/missing value
    instead of a list (a real failure mode without a strict output schema)."""
    if value is None:
        st.caption(empty_message)
    elif isinstance(value, str):
        st.markdown(value)
    elif isinstance(value, list) and value:
        for item in value:
            st.write(f"- {item}")
    else:
        st.caption(empty_message)


if "portfolio_text" not in st.session_state:
    st.session_state["portfolio_text"] = load_sample(SAMPLE_PORTFOLIO)
if "profile_text" not in st.session_state:
    st.session_state["profile_text"] = load_sample(SAMPLE_PROFILE)
if "portfolio_file_name" not in st.session_state:
    st.session_state["portfolio_file_name"] = "portfolio.csv"
if "profile_file_name" not in st.session_state:
    st.session_state["profile_file_name"] = "client_profile.json"

left, right = st.columns(2, gap="large")

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Portfolio</div>', unsafe_allow_html=True)
    portfolio_upload = st.file_uploader(
        "Upload portfolio file",
        type=["csv", "pdf"],
        accept_multiple_files=False,
        help="Upload a CSV or PDF portfolio export.",
    )
    if portfolio_upload is not None:
        st.session_state["portfolio_file_name"] = portfolio_upload.name
        st.session_state["portfolio_text"] = portfolio_upload.getvalue().decode("utf-8", errors="ignore")
    portfolio_text = st.text_area(
        "Paste portfolio CSV text",
        value=st.session_state["portfolio_text"],
        height=240,
        key="portfolio_text_area",
    )
    st.session_state["portfolio_text"] = portfolio_text
    sample_portfolio_clicked = st.button("Use Sample Portfolio", use_container_width=True)
    if sample_portfolio_clicked:
        st.session_state["portfolio_text"] = load_sample(SAMPLE_PORTFOLIO)
        st.session_state["portfolio_file_name"] = "portfolio.csv"
        st.rerun()
    st.caption(f"Current source: {st.session_state['portfolio_file_name']}")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Client Profile</div>', unsafe_allow_html=True)
    profile_upload = st.file_uploader(
        "Upload client profile",
        type=["json"],
        accept_multiple_files=False,
        help="Upload a JSON client profile.",
    )
    if profile_upload is not None:
        st.session_state["profile_file_name"] = profile_upload.name
        st.session_state["profile_text"] = profile_upload.getvalue().decode("utf-8", errors="ignore")
    profile_text = st.text_area(
        "Paste client profile JSON",
        value=st.session_state["profile_text"],
        height=240,
        key="profile_text_area",
    )
    st.session_state["profile_text"] = profile_text
    sample_profile_clicked = st.button("Use Sample Profile", use_container_width=True)
    if sample_profile_clicked:
        st.session_state["profile_text"] = load_sample(SAMPLE_PROFILE)
        st.session_state["profile_file_name"] = "client_profile.json"
        st.rerun()
    st.caption(f"Current source: {st.session_state['profile_file_name']}")
    st.markdown('</div>', unsafe_allow_html=True)

st.write("")

run_clicked = st.button("Generate Review", type="primary", use_container_width=True)

agent = PortfolioReviewAgent()


def portfolio_payload(upload, text: str, fallback_name: str) -> tuple[str, bytes]:
    if upload is not None:
        return upload.name, upload.getvalue()
    return fallback_name, text.encode("utf-8")


if run_clicked:
    portfolio_name, portfolio_bytes = portfolio_payload(
        portfolio_upload,
        st.session_state["portfolio_text"],
        st.session_state["portfolio_file_name"],
    )
    profile_name, profile_bytes = portfolio_payload(
        profile_upload,
        st.session_state["profile_text"],
        st.session_state["profile_file_name"],
    )

    with st.spinner("Analyzing portfolio..."):
        result = agent.run(
            portfolio_name=portfolio_name,
            portfolio_bytes=portfolio_bytes,
            client_profile_name=profile_name,
            client_profile_bytes=profile_bytes,
        )

    status = result.get("status", "error")

    if status != "success":
        st.error(result.get("error", "Unable to generate review."))

        workflow_note = result.get("workflow_note", "")
        if workflow_note:
            st.info(workflow_note)

        decision_log = result.get("decision_log")
        if decision_log:
            with st.expander("Agent Decision Log", expanded=True):
                render_list_or_text(decision_log)

        st.stop()

    report = result["report"]
    parser_result = result["parser_result"]
    profile_result = result["profile_result"]
    analysis = result["analysis"]
    runtime = result.get("runtime", "unknown")
    workflow_note = result.get("workflow_note", "")

    top = st.container(border=True)
    with top:
        st.markdown('<div class="section-label">Portfolio Review</div>', unsafe_allow_html=True)
        st.caption(f"Runtime: {'OpenAI Agents SDK' if runtime == 'openai_agents_sdk' else 'Fallback'}")
        if workflow_note:
            st.caption(workflow_note)
        st.subheader(report["title"])
        st.write(report["summary"])

    metrics_left, metrics_right = st.columns(2, gap="large")
    with metrics_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Risks</div>', unsafe_allow_html=True)
        render_list_or_text(report.get("risks"), "No risks reported.")
        st.markdown('</div>', unsafe_allow_html=True)
    with metrics_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Recommendations</div>', unsafe_allow_html=True)
        render_list_or_text(report.get("recommendations"), "No recommendations reported.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Talking Points</div>', unsafe_allow_html=True)
    render_list_or_text(report.get("talking_points"), "No talking points reported.")
    st.markdown('</div>', unsafe_allow_html=True)

    if parser_result.get("warnings"):
        st.warning("Parser warnings: " + "; ".join(parser_result["warnings"]))
    if profile_result.get("warnings"):
        st.warning("Profile warnings: " + "; ".join(profile_result["warnings"]))

    with st.expander("Portfolio Metrics", expanded=False):
        st.markdown("**Asset Allocation (%)**")
        st.json(analysis.get("asset_allocation", {}))

        st.markdown("**Sector Exposure (%)**")
        st.json(analysis.get("sector_exposure", {}))

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Top Holding", analysis.get("top_holding") or "N/A")
            st.metric("Top Holding Weight", f"{analysis.get('top_holding_weight', 0.0):.2f}%")
            st.metric("Top 3 Weight", f"{analysis.get('top_three_weight', 0.0):.2f}%")
        with col2:
            st.metric("Concentration Risk", analysis.get("concentration_risk", "N/A"))
            st.metric("HHI", f"{analysis.get('hhi', 0.0):.4f}")
            st.metric("Expense Ratio", f"{analysis.get('expense_ratio', 0.0):.2f}%")

    with st.expander("Structured JSON", expanded=False):
        st.json(result["structured_json"])

    with st.expander("Agent Decision Log", expanded=False):
        render_list_or_text(result.get("decision_log"), "No decision log recorded.")

    st.download_button(
        "Download structured report",
        data=json.dumps(result["structured_json"], indent=2),
        file_name="portfolio_review.json",
        mime="application/json",
        use_container_width=True,
    )