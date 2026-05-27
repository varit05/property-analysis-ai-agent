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
