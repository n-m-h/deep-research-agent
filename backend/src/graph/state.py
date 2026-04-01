"""
Research State definition for LangGraph workflow
"""
from typing import TypedDict, List, Optional, Annotated
import operator


class SubTask(TypedDict):
    id: int
    title: str
    intent: str
    query: str
    search_results: List[dict]
    summary: str
    source_urls: List[str]


def _merge_subtasks(existing: List[SubTask], new: List[SubTask]) -> List[SubTask]:
    """Merge subtasks - new list replaces existing (used for partial updates)"""
    if not existing:
        return new
    if not new:
        return existing
    
    # Build index map from new tasks
    new_map = {t["id"]: t for t in new}
    
    # Merge: update existing tasks with new data, keep unchanged ones
    merged = []
    for task in existing:
        if task["id"] in new_map:
            merged_task = {**task}
            merged_task.update(new_map[task["id"]])
            merged.append(merged_task)
        else:
            merged.append(task)
    
    # Add any new tasks not in existing
    existing_ids = {t["id"] for t in existing}
    for task in new:
        if task["id"] not in existing_ids:
            merged.append(task)
    
    return merged


class ResearchState(TypedDict):
    query: str
    sub_tasks: Annotated[List[SubTask], _merge_subtasks]
    current_task_index: int
    draft_report: str
    critique: str
    final_report: str
    iterations: int
    status: str
    error: Optional[str]
