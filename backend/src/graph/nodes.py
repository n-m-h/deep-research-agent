"""
LangGraph nodes for the research workflow
"""
import json
import re
import logging
from typing import List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage

from .state import ResearchState, SubTask
from ..services.search import SearchService
from ..prompts import (
    todo_planner_instructions,
    task_summarizer_instructions,
    report_writer_instructions,
)

logger = logging.getLogger(__name__)

search_service = SearchService()


def decompose_topic(state: ResearchState, llm) -> dict:
    """Node: Decompose research query into sub-tasks"""
    from datetime import datetime
    current_date = datetime.now().strftime("%Y年%m月%d日")

    prompt = todo_planner_instructions.format(
        current_date=current_date,
        research_topic=state["query"],
    )

    messages = [
        SystemMessage(content="你是一个研究规划专家，擅长将复杂的研究主题分解为清晰的子任务。"),
        HumanMessage(content=prompt),
    ]

    response = llm.invoke(messages).content
    tasks = _extract_tasks(response)

    sub_tasks: List[SubTask] = []
    for idx, item in enumerate(tasks, start=1):
        sub_tasks.append({
            "id": idx,
            "title": item["title"],
            "intent": item["intent"],
            "query": item["query"],
            "search_results": [],
            "summary": "",
            "source_urls": [],
        })

    logger.info(f"Decomposed query into {len(sub_tasks)} sub-tasks")
    return {"sub_tasks": sub_tasks, "current_task_index": 0}


def search_sub_task(state: ResearchState) -> dict:
    """Node: Search for a single sub-task (called via Send API for parallelism)"""
    idx = state["current_task_index"]
    sub_tasks = state["sub_tasks"]

    if idx >= len(sub_tasks):
        return {}

    task = sub_tasks[idx]
    logger.info(f"Searching for task {idx + 1}/{len(sub_tasks)}: {task['title']}")

    results = search_service.search(task["query"])
    
    # Create updated copy of the specific task
    updated_task = {**task}
    updated_task["search_results"] = results or []
    updated_task["source_urls"] = [r.get("url", "") for r in (results or [])]

    # Build updated sub_tasks list
    updated_sub_tasks = list(sub_tasks)
    updated_sub_tasks[idx] = updated_task

    return {"sub_tasks": updated_sub_tasks}


def summarize_tasks(state: ResearchState, llm) -> dict:
    """Node: Summarize all sub-task search results"""
    sub_tasks = list(state["sub_tasks"])

    for idx, task in enumerate(sub_tasks):
        if not task.get("search_results"):
            sub_tasks[idx] = {**task, "summary": "未找到相关信息"}
            continue

        formatted_sources = _format_sources(task["search_results"])
        prompt = task_summarizer_instructions.format(
            task_title=task["title"],
            task_intent=task["intent"],
            task_query=task["query"],
            search_results=formatted_sources,
        )

        messages = [
            SystemMessage(content="你是一个任务总结专家，擅长从搜索结果中提取关键信息。"),
            HumanMessage(content=prompt),
        ]

        summary = llm.invoke(messages).content
        sub_tasks[idx] = {**task, "summary": summary}
        logger.info(f"Summarized task {idx + 1}: {task['title']}")

    return {"sub_tasks": sub_tasks}


def generate_report(state: ResearchState, llm) -> dict:
    """Node: Generate the research report"""
    sub_tasks = state["sub_tasks"]
    formatted_summaries = _format_summaries(sub_tasks)

    prompt = report_writer_instructions.format(
        research_topic=state["query"],
        task_summaries=formatted_summaries,
    )

    messages = [
        SystemMessage(content="你是一个报告撰写专家，擅长整合信息并生成结构化的报告。"),
        HumanMessage(content=prompt),
    ]

    report = llm.invoke(messages).content
    logger.info("Report generation completed")
    return {"draft_report": report}


def reflect_report(state: ResearchState, llm) -> dict:
    """Node: Review and critique the draft report"""
    draft = state["draft_report"]
    query = state["query"]

    critique_prompt = f"""请审查以下研究报告的质量。

研究主题：{query}

报告内容：
{draft}

请从以下方面评估：
1. **覆盖度**：是否全面覆盖了研究主题的各个方面？
2. **准确性**：是否有事实性错误或幻觉？
3. **结构**：报告结构是否清晰、逻辑是否连贯？
4. **引用**：来源引用是否充分？
5. **改进建议**：具体指出需要改进的地方。

请以以下格式回复：
VERDICT: APPROVED 或 NEEDS_REVISION
ISSUES: [具体问题列表]
SUGGESTIONS: [具体改进建议]
"""

    messages = [
        SystemMessage(content="你是一个报告审查专家，擅长评估研究报告的质量。"),
        HumanMessage(content=critique_prompt),
    ]

    critique = llm.invoke(messages).content
    needs_revision = "NEEDS_REVISION" in critique.upper()
    logger.info(f"Reflection result: {'NEEDS_REVISION' if needs_revision else 'APPROVED'}")
    return {"critique": critique}


def revise_report(state: ResearchState, llm) -> dict:
    """Node: Revise the report based on critique"""
    draft = state["draft_report"]
    critique = state["critique"]
    query = state["query"]

    revise_prompt = f"""请根据以下审查意见修改研究报告。

研究主题：{query}

原报告：
{draft}

审查意见：
{critique}

请修改报告，解决所有指出的问题。返回完整的修改后报告。
"""

    messages = [
        SystemMessage(content="你是一个报告修改专家，擅长根据反馈改进报告质量。"),
        HumanMessage(content=revise_prompt),
    ]

    revised = llm.invoke(messages).content
    iterations = state.get("iterations", 0) + 1
    logger.info(f"Report revised (iteration {iterations})")
    return {"draft_report": revised, "iterations": iterations}


def finalize_report(state: ResearchState) -> dict:
    """Node: Finalize the report"""
    return {"final_report": state["draft_report"], "status": "completed"}


def should_continue(state: ResearchState) -> str:
    """Router: Decide whether to continue revising or finalize"""
    critique = state.get("critique", "")
    iterations = state.get("iterations", 0)

    if "APPROVED" in critique.upper():
        return "finalize"
    if iterations >= 2:
        return "finalize"
    return "revise"


def fan_out_search(state: ResearchState) -> list:
    """Router: Fan out parallel search tasks using Send API"""
    from langgraph.types import Send
    return [
        Send("search_sub_task", {**state, "current_task_index": i})
        for i in range(len(state["sub_tasks"]))
    ]


# ── Helper functions ──────────────────────────────────────────────────

def _extract_tasks(response: str) -> List[dict]:
    """Extract JSON from LLM response"""
    response = response.strip()
    response = re.sub(r'^```json\s*', '', response)
    response = re.sub(r'^```\s*', '', response)
    response = re.sub(r'\s*```$', '', response)
    response = response.replace('\u201c', '"').replace('\u201d', '"')
    response = response.replace('\u2018', "'").replace('\u2019', "'")

    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"无法从响应中提取JSON: {response[:300]}")


def _format_sources(search_results: List[dict]) -> str:
    """Format search results for prompt"""
    formatted = []
    for idx, result in enumerate(search_results, start=1):
        formatted.append(
            f"[{idx}] {result.get('title', 'Unknown')}\n"
            f"URL: {result.get('url', '')}\n"
            f"摘要: {result.get('snippet', '')}\n"
        )
    return "\n".join(formatted)


def _format_summaries(sub_tasks: List[SubTask]) -> str:
    """Format task summaries for report generation"""
    formatted = []
    for idx, task in enumerate(sub_tasks, start=1):
        formatted.append(
            f"## 任务{idx}：{task['title']}\n\n"
            f"**意图**：{task['intent']}\n\n"
            f"{task['summary']}\n\n"
            f"**来源**：\n"
        )
        for url in task.get("source_urls", []):
            if url:
                formatted.append(f"- {url}\n")
        formatted.append("\n")
    return "".join(formatted)
