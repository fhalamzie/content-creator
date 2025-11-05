"""
Robust JSON Parser

Handles JSON extraction from LLM responses with various fallback strategies.
"""

import json
import re
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_json_from_text(text: str, expected_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract JSON from text using multiple fallback strategies.

    Strategies (in order):
    1. Direct JSON parsing (text is already valid JSON)
    2. Extract from markdown code fences (```json...```)
    3. Extract from first {...} or [...] block
    4. Try to fix common JSON issues (trailing commas, single quotes)

    Args:
        text: Text containing JSON (possibly with extra content)
        expected_schema: Optional schema for validation (not used yet, future enhancement)

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If no valid JSON could be extracted
    """
    logger.debug("extracting_json", text_length=len(text), has_schema=expected_schema is not None)

    # Strategy 1: Direct parsing
    try:
        result = json.loads(text.strip())
        logger.info("json_extracted_direct", strategy="direct")
        return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code fence
    code_fence_pattern = r'```(?:json)?\s*\n(.*?)\n```'
    matches = re.findall(code_fence_pattern, text, re.DOTALL)
    if matches:
        for match in matches:
            try:
                result = json.loads(match.strip())
                logger.info("json_extracted_code_fence", strategy="code_fence")
                return result
            except json.JSONDecodeError:
                continue

    # Strategy 3: Extract from first {...} or [...] block
    # Find the first { or [ and match to its closing bracket
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested objects
        r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]',  # Nested arrays
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    result = json.loads(match.strip())
                    logger.info("json_extracted_regex", strategy="regex", pattern=pattern)
                    return result
                except json.JSONDecodeError:
                    continue

    # Strategy 4: Try to fix common issues
    # Remove trailing commas before } or ]
    cleaned_text = re.sub(r',\s*([}\]])', r'\1', text)
    # Replace single quotes with double quotes (risky, but common issue)
    cleaned_text = cleaned_text.replace("'", '"')

    try:
        result = json.loads(cleaned_text.strip())
        logger.info("json_extracted_cleaned", strategy="cleaned")
        return result
    except json.JSONDecodeError as e:
        logger.error("json_extraction_failed", error=str(e), text_preview=text[:200])
        raise ValueError(f"Could not extract valid JSON from text: {e}")


def schema_to_json_prompt(schema: Dict[str, Any]) -> str:
    """
    Convert JSON schema to human-readable prompt instructions.

    Args:
        schema: JSON schema dict

    Returns:
        Formatted prompt text describing the expected JSON structure
    """
    if schema.get('type') != 'object':
        return "Output valid JSON"

    properties = schema.get('properties', {})
    required = schema.get('required', [])

    lines = ["Output valid JSON with this EXACT structure:"]
    lines.append("{")

    for i, (key, value) in enumerate(properties.items()):
        prop_type = value.get('type', 'any')
        description = value.get('description', '')
        is_required = key in required

        # Format field
        field_str = f'  "{key}": '

        if prop_type == 'array':
            items_type = value.get('items', {}).get('type', 'object')
            field_str += f'[{items_type}...]'
        elif prop_type == 'object':
            field_str += '{...}'
        elif prop_type == 'string':
            field_str += '"string"'
        elif prop_type == 'number':
            field_str += '0.0'
        elif prop_type == 'integer':
            field_str += '0'
        elif prop_type == 'boolean':
            field_str += 'true'
        else:
            field_str += 'null'

        # Add comma if not last
        if i < len(properties) - 1:
            field_str += ','

        # Add description comment
        if description:
            field_str += f'  // {description}'

        # Mark required
        if is_required:
            field_str += ' (REQUIRED)'

        lines.append(field_str)

    lines.append("}")
    lines.append("")
    lines.append("IMPORTANT: Output ONLY valid JSON, no additional text or markdown.")

    return "\n".join(lines)
