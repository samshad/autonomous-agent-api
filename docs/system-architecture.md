# 🤖 Autonomous E-Commerce Agent API: Architecture & Implementation Blueprint

## 1. Executive Summary & Value Proposition

While Retrieval-Augmented Generation (RAG) empowers AI to *read* context, the next evolution of AI engineering is **Agentic Workflows**—empowering AI to *take action*.

This project is a fully asynchronous, stateless API that functions as an autonomous customer support agent for a simulated e-commerce platform. Users submit natural language requests (e.g., *"Cancel my order #12345"*). The AI uses **Function Calling (Tool Use)** to autonomously query a PostgreSQL database via SQLAlchemy, evaluate business logic, execute state-changing actions, and report back to the user.

**Portfolio Impact:** This project demonstrates advanced backend systems design, strict schema validation, the ReAct (Reason + Act) loop paradigm, and adherence to SOLID engineering principles—proving the ability to build safe, deterministic AI systems that integrate with live, cloud-native relational databases.

---

## 2. Core Capabilities (The MVP)

* **Natural Language to Action:** Translates conversational user intents into precise, deterministic database queries and mutations.
* **Strict Schema Validation:** Utilizes Pydantic to enforce rigid data contracts. The LLM cannot crash the database by hallucinating invalid arguments or missing required fields.
* **The ReAct Orchestration Loop:** The agent autonomously cycles through reasoning, tool execution, and observation phases until the user's goal is resolved or safely rejected based on business rules.
* **100% Asynchronous I/O:** Built entirely on Python's `asyncio` and SQLAlchemy's async ORM to ensure database reads, writes, and external LLM network calls never block the API event loop.

---

## 3. Technology Stack

* **Framework:** FastAPI (Python 3.12+)
* **Database:** Neon Serverless Postgres.
* **ORM & Driver:** SQLAlchemy 2.0 (Async ORM) with `asyncpg` (Provides high-performance, non-blocking connection pooling to Postgres).
* **AI / LLM:** Local Ollama (`llama3.1` or `qwen2.5`) via `httpx.AsyncClient`.
* **Data Validation:** Pydantic v2 (Crucial for generating dynamic JSON Schemas for LLM tool binding).
* **Package Management:** `uv` (for lightning-fast dependency resolution).
* **Observability:** `structlog` (for structured, JSON-formatted telemetry).

---

## 4. System Architecture

The system strictly adheres to **Domain-Driven Design (DDD)**, separating the application into four distinct, decoupled layers:

1. **Presentation Layer (`api/`):** The FastAPI HTTP boundary. Responsible *only* for receiving payloads, authenticating (if applicable), and routing to the orchestrator.
2. **AI Orchestration Layer (`agent/`):** The "Brain." Manages the ReAct `while` loop, communicates with the LLM API, and dynamically maps LLM tool requests to actual Python functions.
3. **Domain & Service Layer (`services/`):** The business logic. Determines *if* an action is allowed (e.g., rejecting an order cancellation if the status is already 'shipped').
4. **Data Access Layer (`repository/`):** The SQLAlchemy ORM boundary. Abstracts database complexity, SQL syntax, and session management away from the business logic.

---

## 5. Core Design Principles (SOLID)

To ensure this codebase is enterprise-grade, it is built on strict software design principles:

* **Open/Closed Principle (OCP):** The system features a dynamic `ToolRegistry`. To grant the AI a new capability (e.g., `refund_customer`), an engineer simply writes the function and tags it with a `@tool` decorator. The core ReAct loop requires **zero modifications** to adopt the new feature.
* **Dependency Inversion Principle (DIP):** The `AgentEngine` does not hardcode connections to Ollama or OpenAI. It depends on an abstract `LLMClient` interface, making it trivial to swap AI providers or mock the LLM entirely during unit testing.
* **Single Responsibility Principle (SRP):** Functions that execute business logic (`commerce.py`) have zero awareness of the LLM. Functions that talk to the LLM (`engine.py`) have zero awareness of SQLAlchemy syntax.

---

## 6. Directory Structure

```text
autonomous-agent-api/
├── .env.example
├── .gitignore
├── pyproject.toml             # Managed by `uv`
├── README.md
├── tests/
│   ├── conftest.py            # Test database & mock LLM fixtures
│   ├── unit/                  # Tests for Tool Registry & business logic
│   └── integration/           # Tests for the ReAct loop and DB state
└── src/
    └── agent_api/
        ├── __init__.py
        ├── main.py            # FastAPI application factory & lifecycle
        │
        ├── api/               # 🌐 Presentation Layer
        │   ├── dependencies.py# DI: get_db_session(), get_agent()
        │   └── routes/
        │       └── chat.py    # POST /api/v1/chat
        │
        ├── core/              # ⚙️ Infrastructure & Config
        │   ├── config.py      # Pydantic BaseSettings
        │   ├── database.py    # SQLAlchemy AsyncEngine & sessionmaker
        │   ├── exceptions.py  # Custom HTTP & Agent errors
        │   └── logger.py      # structlog configuration
        │
        ├── models/            # 📦 Data Contracts & ORM
        │   ├── domain.py      # SQLAlchemy Declarative Base (Order, User)
        │   ├── schemas.py     # HTTP Request/Response Pydantic models
        │   └── agent.py       # LLM payload schemas (Message, ToolCall)
        │
        ├── repository/        # 🗄️ Data Access Layer (SQLAlchemy Sessions)
        │   └── order_repo.py  # async ORM queries (select, update)
        │
        ├── services/          # 💼 Business Logic Layer
        │   └── commerce.py    # Validates rules (e.g., "Cannot cancel shipped order")
        │
        └── agent/             # 🧠 AI Orchestration Layer
            ├── engine.py      # The ReAct `while` loop
            ├── llm_client.py  # httpx.AsyncClient wrapper for Ollama/Cloud APIs
            ├── registry.py    # The `@tool` decorator & JSON Schema generator
            └── tools.py       # The actual functions exposed to the LLM

```

---

## 7. Development Roadmap & Execution Map

### Phase 1: Infrastructure & Data Access (The Foundation)

* **Goal:** Establish the FastAPI environment and async SQLAlchemy connection to Neon Postgres.
* **Deliverables:**
* Initialize project with `uv`.
* Create `core/database.py` to handle the SQLAlchemy `create_async_engine` and `async_sessionmaker`.
* Define SQLAlchemy declarative models in `models/domain.py` (Users, Orders, Products).
* Write an initialization script to `create_all()` tables and seed dummy data.
* Implement `repository/order_repo.py` using SQLAlchemy `select()` and `update()` constructs.



### Phase 2: Domain Services & Tool Definition (The Actions)

* **Goal:** Build the heavily-typed Python functions that the LLM will eventually trigger.
* **Deliverables:**
* Create `services/commerce.py` (e.g., `cancel_order` with strict business logic to prevent canceling shipped items).
* Create `agent/tools.py` containing wrapped service functions with **exhaustive docstrings** and strict Pydantic type hints so the LLM knows exactly how to use them.



### Phase 3: The Dynamic Tool Registry (The Magic)

* **Goal:** Bridge Python functions to LLM-readable JSON schemas automatically.
* **Deliverables:**
* Build the `ToolRegistry` class in `agent/registry.py`.
* Create a custom `@tool` decorator that leverages Pydantic to inspect function signatures and generate OpenAI/Ollama compliant JSON Tool Schemas on the fly.



### Phase 4: The ReAct Engine (The Brain)

* **Goal:** Orchestrate the conversation and tool execution loop.
* **Deliverables:**
* Implement `agent/llm_client.py` (`httpx.AsyncClient` wrapper).
* Build the `AgentEngine` (`agent/engine.py`).
* Implement the core `while` loop: Parse user prompt -> Send context to LLM -> Intercept `tool_calls` -> Execute tool from Registry -> Feed result back to LLM -> Return final natural language response.



### Phase 5: API Layer & Integration Testing

* **Goal:** Expose the agent via HTTP and verify end-to-end functionality.
* **Deliverables:**
* Create `api/routes/chat.py` (`POST /chat`).
* Wire up dependency injection (`get_db_session`, `get_engine`).
* Write `pytest` integration tests proving that sending *"Cancel my order #123"* successfully updates the Neon Postgres database via SQLAlchemy and returns a natural language confirmation.

