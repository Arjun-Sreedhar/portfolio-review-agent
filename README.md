# Portfolio Review Agent

An AI-powered portfolio review assistant for wealth advisors built using the **OpenAI Agents SDK** and **Streamlit**.

The application helps advisors prepare for client review meetings by combining deterministic portfolio analysis with AI-generated advisor insights. Instead of manually reviewing brokerage statements, calculating portfolio metrics, and preparing meeting notes, advisors can upload a portfolio and client profile to receive an advisor-ready review along with structured JSON output.

---

## Features

- Upload or paste a portfolio (CSV or supported brokerage statement)
- Upload or paste a client profile (JSON)
- Deterministic portfolio analysis:
  - Asset allocation
  - Sector exposure
  - Concentration risk
  - Weighted expense ratio
- AI-generated advisor review
- Advisor meeting talking points
- Structured JSON output for downstream systems
- Graceful handling of incomplete or malformed inputs
- Human-in-the-loop workflow (no autonomous investment decisions)

---

## Architecture

The application follows an agentic workflow where the OpenAI Agent coordinates specialized tools instead of relying on a single LLM prompt.

```text
Advisor
   │
   ▼
Upload Portfolio + Client Profile
   │
   ▼
OpenAI Agent (Coordinator)
   │
   ▼
Portfolio Parser Tool
   │
   ▼
Portfolio Analysis Tool
   │
   ▼
Portfolio Review Generator
   │
   ├────────► Advisor Summary
   │
   └────────► Structured JSON
```

The OpenAI Agent orchestrates the workflow by invoking specialized tools, interpreting their outputs, and deciding whether to continue, stop, or surface warnings before generating the final advisor review.

---

## Tool Responsibilities

### Portfolio Parser

- Parses portfolio CSV/PDF
- Normalizes portfolio data
- Extracts structured holdings
- Reports parsing warnings and failures

### Portfolio Analysis

Performs deterministic financial calculations:

- Asset allocation
- Sector exposure
- Concentration risk
- Weighted expense ratio

No LLM is used for financial calculations.

### Portfolio Review Generator

Combines the structured portfolio analysis with the client profile to generate:

- Portfolio summary
- Risk explanations
- Advisor-reviewable recommendations
- Meeting talking points

---

## Project Structure

```text
portfolio-review-agent/
│
├── app.py
├── agent.py
├── tools/
│   ├── __init__.py
│   ├── portfolio_parser.py
│   ├── portfolio_analysis.py
│   └── portfolio_review_generator.py
├── sample_data/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Installation

Clone the repository:

```bash
git clone <https://github.com/Arjun-Sreedhar/portfolio-review-agent>
cd portfolio-review-agent
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Add your OpenAI API key:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Run the application:

```bash
streamlit run app.py
```

---

## Sample Test Files

The `sample_data` folder contains synthetic datasets covering different advisor scenarios.

| File | Purpose |
|------|---------|
| `portfolio.csv` | Standard portfolio review |
| `diversified_portfolio.csv` | Diversified portfolio |
| `high_concentration_portfolio.csv` | High concentration risk |
| `high_expense_portfolio.csv` | High expense ratio |
| `partial_portfolio.csv` | Partial parsing with warnings |
| `bad_portfolio.csv` | Parser failure scenario |
| `client_profile.json` | Complete client profile |
| `incomplete_client_profile.json` | Missing client information |
| `conservative_client_profile.json` | Alternative client profile |

---

## Tested Scenarios

The application was tested across multiple synthetic scenarios:

- Normal portfolio review
- High concentration portfolio
- High expense ratio portfolio
- Diversified portfolio
- Partial portfolio parsing
- Complete parser failure
- Incomplete client profile

---

## Agent Decision Policy

The OpenAI Agent follows a structured workflow rather than making unrestricted tool calls.

- Parse the portfolio before performing analysis.
- Stop the workflow if portfolio parsing fails.
- Continue with warnings when partial parsing is acceptable.
- Never assume missing client information.
- Generate more detailed reviews when concentration risk is high.
- Keep the advisor responsible for all investment decisions.

---

## Graceful Failure Handling

The application is designed to fail safely.

Examples include:

- Invalid portfolio files
- Partial portfolio parsing
- Missing client profile fields
- Missing OpenAI API key (falls back to deterministic review generation)

Instead of silently producing incomplete results, the agent surfaces warnings or stops the workflow with a clear explanation when appropriate.

---

## Mocked Integrations

To keep the project focused on the agent workflow, the following integrations are mocked:

- Live market data
- Brokerage platform integration
- CRM storage
- Trade execution

---

## Technology Stack

- Python
- Streamlit
- OpenAI Agents SDK
- OpenAI Python SDK
- Pandas
- python-dotenv

---

## Design Principles

This project intentionally separates deterministic computation from AI reasoning.

- Portfolio calculations are performed using deterministic Python code.
- The OpenAI Agent orchestrates the workflow and interprets tool outputs.
- The LLM is responsible for contextual reasoning and advisor-facing narrative—not numerical calculations.
- The advisor remains responsible for all investment decisions.

---

## License

Created as part of the Mili Forward Deployed Engineer take-home assignment.