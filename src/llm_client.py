import json
import logging
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError

# Adjust imports to match your project configuration
from src.config import GEMINI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def call_structured(
    system_prompt: str,
    user_prompt: str,
    tool_schema: dict,
    tool_name: str,
    max_retries: int = 2,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> dict:
    """
    Forces the Gemini model to adhere to `tool_schema` and respond with a structured JSON object.
    Returns the parsed dictionary matching the schema.
    """
    client = get_client()
    last_err = None

    # Configure Gemini structured JSON output mode
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        response_schema=tool_schema,
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_prompt,
                config=config,
            )

            # Extract parsed dictionary if available, or parse text string as JSON
            if hasattr(response, "parsed") and response.parsed is not None:
                if isinstance(response.parsed, dict):
                    return response.parsed

            if response.text:
                return json.loads(response.text)

            raise ValueError("Model returned an empty response")

        except (APIError, json.JSONDecodeError, ValueError) as e:
            last_err = e
            logger.warning(
                "Attempt %d/%d for '%s' failed: %s",
                attempt + 1,
                max_retries + 1,
                tool_name,
                e,
            )
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(
        f"LLM call '{tool_name}' failed after {max_retries + 1} attempts: {last_err}"
    ) from last_err