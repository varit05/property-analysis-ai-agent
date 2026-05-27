# Property Analysis AI Agent

Property analysis, featuring AI-powered analysis via DeepAgent with a human-in-the-loop review workflow.

Users submit a free-form natural language query (e.g. _"Analyse property price trends in GU1 over the last 3 years"_). The agent parses the query, decides which skills to use, and executes them as a **background task**. Trace steps are streamed in real-time via **Server-Sent Events (SSE)**. Once complete, the result enters a **pending_review** state where a human must manually **accept or reject** the suggestion before it is considered final.

## Quick Start

### Local Development

```bash
# Install dependencies
pip install server/.

# Run the server
uvicorn server.main:app --reload
```

### Linting & Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting.

```bash
# Check for lint errors
ruff check

# Auto-fix lint errors
ruff check --fix

# Format code
ruff format
```

Configuration is in `pyproject.toml` under the `[tool.ruff]` section.

The API will be available at `http://localhost:8000`.

Interactive API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Create a `.env` file in the project root to override defaults:

```env
ENVIRONMENT=development
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4
LOG_LEVEL=INFO
```

For production:

```env
ENVIRONMENT=production
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Running Tests

```bash
# Run tests
pytest server/tests/ -v
```

## Code Formatting

This project uses [Black](https://github.com/psf/black) as its code formatter. All Python files are formatted with the configuration defined in `pyproject.toml` (line length of 88, targeting Python 3.14).

```bash
# Format all Python files
black server/

# Check formatting without making changes (useful for CI)
black --check server/
```

## Architecture Decisions

### 1. LLM-provider-agnostic

    - **Development:** uses Ollama to develop and test the changes to cut down the cost.
    - Productions' first preference is OPENAI while fallback is set to Anthropic. It can be easily switchable.

## 2. Core Components

### 2.1 API Layer (FastAPI)

- **Responsibility:** Manages external interactions, analysis lifecycle, and real-time event streaming.
- **Key Features:** Background task processing for long-running analyses and Server-Sent Events (SSE) for live trace updates.

### 2.2 Agent Orchestrator

The "brain" of the system, implementing a **Plan-Act-Evaluate** loop.

1. **Planning Phase:** Uses an LLM to map a query to a sequence of "Skills" based on YAML metadata.
2. **Execution Phase:** Executes the plan. Uses **Async Execution** to handle I/O-bound data fetching without blocking the server.
3. **Evaluation Phase:** A second LLM pass determines if the gathered data is sufficient to answer the query. If not, it triggers a re-planning loop.
4. **Synthesis Phase:** Final synthesis of research notes and structured chart data.

### 2.3 Skills System

- **Modularity:** Skills are defined in YAML files (`server/api/properties/skills/`), decoupling metadata (description, inputs) from implementation.
- **Dynamic Loading:** The `skills_loader` handles lazy-loading of Python functions, allowing the system to scale its capabilities without modifying the core agent logic.
- **Async Implementation:** Skills leverage `httpx` for non-blocking network calls to Land Registry SPARQL and REST endpoints.

### 2.4 Persistence Layer

- **Analysis Store:** Manages the state of analysis objects (Pending, Running, Completed, Reviewed).
- **Storage:** Currently uses a file-based JSON store for simplicity and local portability.

## 3. Technical Trade-offs

### 3.1 LLM-Driven Planning vs. Fixed Graph Workflows

- **Choice:** LLM-driven planning.
- **Trade-off:**
  - **Pros:** Extremely flexible; can handle unexpected query variations and combine data in novel ways.
  - **Cons:** Non-deterministic; occasionally requires re-planning loops, increasing latency and token costs compared to a hard-coded decision tree.

### 3.2 Skill-Based Modularity vs. Monolithic Integration

- **Choice:** Skill-based modularity via YAML definitions.
- **Trade-off:**
  - **Pros:** New data sources can be added by simply dropping a YAML and a Python function. The LLM "learns" the new tool automatically from its description.
  - **Cons:** Adds an abstraction layer (loader/meta-registry) that must be maintained and kept in sync with the actual code signatures.

### 3.3 Async def Skills vs. Sync Execution

- **Choice:** Full Async Execution
- **Trade-off:**
  - **Pros:** Allows the system to handle many concurrent analyses and fetch data from multiple endpoints efficiently. Essential for the SSE streaming UX.
  - **Cons:** Increases complexity in error handling and requires all downstream libraries (like `httpx`) to be async-compatible.

### 3.4 Plan-Act-Evaluate Pattern vs Re-Act Pattern

- **Choice:** Plan-Act-Evaluate Pattern.
- **Trade-off:**
  - **Pros:** Predictability & Control is High; Can inspect, modify, or block the plan before any action is taken. Perfect for human-in-the-loop validation.
  - **Cons:** High Initial Latency. Significant upfront delay while the plan is generated, but actual execution is often faster and can sometimes be parallelized.

### 3.5 File-Based JSON Storage vs. Relational Database (PostgreSQL)

- **Choice:** File-based JSON (`analyses.json`).
- **Trade-off:**
  - **Pros:** Zero configuration; perfect for a prototype or local tool. Easy to inspect and debug.
  - **Cons:** Not suitable for high-concurrency environments; lacks row-level locking and advanced querying capabilities.
