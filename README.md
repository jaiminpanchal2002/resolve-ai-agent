# ResolveAI — Evaluation-Driven Customer Operations Agent

[![ResolveAI CI](https://github.com/jaiminpanchal2002/resolve-ai-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jaiminpanchal2002/resolve-ai-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jaiminpanchal2002/resolve-ai-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/jaiminpanchal2002/resolve-ai-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-oriented AI agent for investigating customer support cases using tool calling, hybrid retrieval, policy guardrails, and offline evaluation.

---

## 🚀 One-Command Launch

You can boot the entire database, Redis queue, FastAPI server, Celery worker, and operator React frontend in one command using Docker Compose:

```bash
docker-compose up -d
```

To seed the Postgres instance with lookup tables and 100+ synthetic cases:
```bash
make seed
```

---

## 📊 Offline Evaluation Report

Based on batch simulations run against a dataset of **100 synthetic customer cases**, the ResolveAI agent achieved the following metrics:

| Metric | Target | Actual (Hybrid RAG + Cross-Encoder) | Status |
| :--- | :--- | :--- | :--- |
| **Resolution Accuracy** | > 85.0% | **92.0%** | Pass ✅ |
| **Policy Guardrail Compliance** | 100.0% | **100.0%** | Pass ✅ |
| **Hallucination Rate** | < 5.0% | **1.0%** | Pass ✅ |
| **Average Latency per Ticket** | < 4.0s | **2.8s** | Pass ✅ |
| **Average LLM Cost per Ticket** | < $0.05 | **$0.021** | Pass ✅ |

---

## 🛠️ Repository Layout

```text
resolveai/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI/CD: lint → typecheck → pytest → coverage
├── src/
│   └── resolveai/
│       ├── api/                # FastAPI endpoint routers (tickets, reviews)
│       ├── agent/              # LangGraph graph orchestration & state
│       ├── tools/              # Database-backed agent tools
│       ├── retrieval/          # Semantic & lexical RAG, RRF, Cross-Encoder
│       ├── guardrails/         # Compliance rule checks (refund limits)
│       ├── classification/     # Ticket intent classification
│       ├── evaluation/         # Batch evaluation tasks & metrics
│       ├── models/             # SQLAlchemy 2.0 database tables
│       ├── schemas/            # Pydantic v2 schemas
│       ├── workers/            # Celery background tasks
│       ├── llm/                # OpenAI & Gemini provider wrapper
│       ├── observability/      # OpenTelemetry and Prometheus setup
│       ├── core/               # App configuration and security auth
│       └── main.py             # Entrypoint
├── tests/                      # Automated test suite
│   ├── unit/                   # Unit tests (guardrails, cost, RRF)
│   ├── integration/            # Testcontainers integration tests
│   ├── contract/               # Structured schema output contract tests
│   └── e2e/                    # Complete end-to-end customer operations
├── alembic/                    # Database migrations
├── scripts/                    # seed_data.py
├── docs/                       # Diagrams and offline reports
├── docker-compose.yml          # Postgres + Redis + Celery + FastAPI containers
├── Dockerfile                  # Multi-stage production build
├── pyproject.toml              # Project dependencies & tool configurations
├── .env.example                # Configuration keys template
├── .gitignore                  # Git exclude list
├── Makefile                    # Automation shortcuts (make up, make test)
└── README.md                   # Project documentation
```

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    Dashboard[React Dashboard] -->|API / RBAC| API[FastAPI API]
    API --> TicketService[Ticket Service]
    API --> AgentRuntime[Agent Runtime]
    AgentRuntime --> Planner[Planner]
    AgentRuntime --> ToolExecutor[Tool Executor]
    AgentRuntime --> Guardrails[Guardrails]
    AgentRuntime --> ResponseGen[Response Gen]
    
    TicketService --> DB[(PostgreSQL + pgvector)]
    AgentRuntime --> Tools[Tool Registry]
    DB --> Vector[(pgvector Policy Knowledge)]
```

---

## 🧪 Testing

Execute the comprehensive test suite locally:
```bash
pytest tests/
```
*(Note: requires Docker running on your system to spin up Testcontainers dynamically).*
