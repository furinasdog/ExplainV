"""
Parse LLM responses for the code-generation step.

The LLM is expected to return JSON in this shape::

    {
        "Scene Name": "XXXXScene",
        "Code": "import ..."
    }

The parser handles common LLM quirks:
- JSON wrapped in markdown code fences (```json ... ```)
- Leading/trailing whitespace
- Escaped newlines inside the Code string
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GeneratedScene:
    """Parsed result from the code-generation LLM call."""

    scene_name: str
    code: str


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Raised when the LLM response cannot be parsed into valid code."""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if present.

    Handles:
        ```json ... ```
        ``` ... ```
    """
    # Pattern: optional ```[lang]\n ... \n```
    pattern = r"^```(?:json|JSON)?\s*\n(.*?)\n\s*```\s*$"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _try_parse_json(text: str) -> Optional[dict]:
    """Attempt to parse *text* as JSON, returning None on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_json_from_text(text: str) -> Optional[dict]:
    """Try multiple strategies to extract JSON from an LLM response."""

    # Strategy 1: Direct parse
    result = _try_parse_json(text)
    if result is not None:
        return result

    # Strategy 2: Strip code fences then parse
    stripped = _strip_code_fences(text)
    result = _try_parse_json(stripped)
    if result is not None:
        return result

    # Strategy 3: Find JSON object by braces
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        result = _try_parse_json(brace_match.group())
        if result is not None:
            return result

    return None


def parse_code_generation_response(response: str) -> GeneratedScene:
    """Parse the LLM's code-generation response into a :class:`GeneratedScene`.

    Args:
        response: Raw text response from the LLM.

    Returns:
        A :class:`GeneratedScene` with ``scene_name`` and ``code``.

    Raises:
        ParseError: If the response cannot be parsed.
    """
    if not response or not response.strip():
        raise ParseError("LLM returned an empty response")

    data = _extract_json_from_text(response)

    if data is None:
        logger.error("Failed to parse LLM response as JSON:\n%s", response[:500])
        raise ParseError(
            "Could not extract valid JSON from LLM response. "
            "Check the logs for the raw response."
        )

    # Validate required fields
    scene_name = data.get("Scene Name")
    code = data.get("Code")

    if not scene_name:
        raise ParseError(
            f"Missing 'Scene Name' in LLM response. Keys found: {list(data.keys())}"
        )
    if not code:
        raise ParseError(
            f"Missing 'Code' in LLM response. Keys found: {list(data.keys())}"
        )

    if not isinstance(code, str):
        raise ParseError(f"'Code' field must be a string, got {type(code).__name__}")

    logger.info("Parsed scene: %s (%d chars of code)", scene_name, len(code))
    return GeneratedScene(scene_name=str(scene_name), code=str(code))
