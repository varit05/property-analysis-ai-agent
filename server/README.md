# Property Analysis API

FastAPI backend for property analysis, featuring AI-powered analysis via DeepAgent with a human-in-the-loop review workflow.

Users submit a free-form natural language query (e.g. _"Analyse property price trends in GU1 over the last 3 years"_). The agent parses the query, decides which skills to use, and executes them as a **background task**. Trace steps are streamed in real-time via **Server-Sent Events (SSE)**. Once complete, the result enters a **pending_review** state where a human must manually **accept or reject** the suggestion before it is considered final.
