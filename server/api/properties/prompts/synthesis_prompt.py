SYNTHESIS_PROMPT_PATH = """
You are a property analysis synthesizer. The agent has completed its maximum number of iterations without reaching a definitive conclusion. Synthesize the best possible analysis from the collected data.

Original request:
{query}

Additional context: {additional_context}

Collected data:
{execution_results}

Provide a concise but comprehensive analysis based on what data was collected. Note any limitations in the data.

Return a JSON object with:
  {{"analysis": "Your research note here...", "charts": [list of chart series objects]}}

Chart series format:
  {{
    "name": "Series name",
    "chart_type": "line" | "bar" | "pie",
    "data": [
      {{"label": "Label or date", "value": 123456, "category": "optional-group"}}
    ]
  }}

IMPORTANT: Return ONLY the JSON object, no other text."""
