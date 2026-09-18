# GridWise — Smart Campus Energy Optimization

An end-to-end HTTP API service built for the **BUP CSE Fest 2026 Hackathon (Online Preliminary)**. The system interprets natural-language operator directives using a Large Language Model (LLM), sanitizes them with deterministic guardrails, and solves a 24-hour campus energy schedule minimizing total grid electricity cost via Linear Programming (HiGHS).

---

## 1. Architecture Overview

```text
Operator Notes (1-3 natural language strings)
        │
        ▼
[ LLM Semantic Interpreter ] (Gemini 1.5 Flash / Groq / OpenAI)
        │
        ▼
[ Deterministic Guardrail Validator ] (Hours 0-23, bounds, factor & schema normalization)
        │
        ▼
[ Mathematical Energy Optimizer ] (SciPy linprog HiGHS - 24h LP Formulation)
        │
        ▼
[ Independent Schedule Replay Validator ] (Balance, rate limits, SOC neutrality)
        │
        ▼
JSON API Response (directive_interpretation, hourly_plan, totals)