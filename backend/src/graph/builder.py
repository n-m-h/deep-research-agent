"""
Build and compile the LangGraph StateGraph for research workflow
"""
import logging
from functools import partial
from typing import List

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from .state import ResearchState
from .nodes import (
    decompose_topic,
    search_sub_task,
    summarize_tasks,
    generate_report,
    reflect_report,
    revise_report,
    finalize_report,
    should_continue,
)

logger = logging.getLogger(__name__)


def _fan_out_router(state: ResearchState) -> List[Send]:
    """Router: Fan out parallel search tasks using Send API"""
    return [
        Send("search_sub_task", {**state, "current_task_index": i})
        for i in range(len(state["sub_tasks"]))
    ]


def _route_after_fan_out(state: ResearchState) -> str:
    """After all parallel searches complete, go to summarize"""
    return "summarize"


def build_research_graph(llm):
    """Build the complete research workflow graph"""

    builder = StateGraph(ResearchState)

    # Wrap nodes that need llm
    decompose_node = partial(decompose_topic, llm=llm)
    summarize_node = partial(summarize_tasks, llm=llm)
    report_node = partial(generate_report, llm=llm)
    reflect_node = partial(reflect_report, llm=llm)
    revise_node = partial(revise_report, llm=llm)

    # Add nodes
    builder.add_node("decompose", decompose_node)
    builder.add_node("fan_out", lambda state: state)
    builder.add_node("search_sub_task", search_sub_task)
    builder.add_node("summarize", summarize_node)
    builder.add_node("generate_report", report_node)
    builder.add_node("reflect", reflect_node)
    builder.add_node("revise", revise_node)
    builder.add_node("finalize", finalize_report)

    # Define edges
    builder.set_entry_point("decompose")
    builder.add_edge("decompose", "fan_out")

    # Fan out to parallel search tasks
    builder.add_conditional_edges(
        "fan_out",
        _fan_out_router,
        ["search_sub_task"],
    )

    # After all searches complete, go to summarize
    builder.add_edge("search_sub_task", "summarize")
    builder.add_edge("summarize", "generate_report")
    builder.add_edge("generate_report", "reflect")

    # Conditional routing after reflection
    builder.add_conditional_edges(
        "reflect",
        should_continue,
        {"revise": "revise", "finalize": "finalize"},
    )

    builder.add_edge("revise", "reflect")
    builder.add_edge("finalize", END)

    graph = builder.compile()
    logger.info("Research graph built successfully")
    return graph
