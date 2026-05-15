"""
Shared utility functions
"""
import json
import re
from typing import List, Dict, Any


def extract_tasks(response: str) -> List[Dict[str, Any]]:
    """Extract JSON task list from LLM response.

    Tries, in order:
    1.  Parse a top-level JSON array  [...]
    2.  Parse the raw string as JSON
    3.  Parse a JSON object {...} that contains a "tasks" key
    """
    response = response.strip()
    response = re.sub(r'^```json\s*', '', response)
    response = re.sub(r'^```\s*', '', response)
    response = re.sub(r'\s*```$', '', response)

    # Replace Unicode smart quotes with straight quotes
    response = response.replace('\u201c', '"').replace('\u201d', '"')
    response = response.replace('\u2018', "'").replace('\u2019', "'")

    # 1. Try to extract a top-level JSON array
    array_match = re.search(r'\[[\s\S]*\]', response)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    # 2. Try the whole string as raw JSON
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 3. Try to extract a JSON object that contains a "tasks" key
    obj_match = re.search(r'\{[\s\S]*\}', response)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            if isinstance(data, dict) and "tasks" in data:
                return data["tasks"]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {response[:300]}")
