"""
LangGraphAgent - LangGraph-based deep research agent
"""
import sys
import os
import json
import logging
from typing import AsyncGenerator

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "HelloAgents")))

from .config import config
from .langgraph_llm import create_chat_model
from .graph.builder import build_research_graph

logger = logging.getLogger(__name__)


class LangGraphAgent:
    """LangGraph-based deep research agent
    
    Uses LangGraph StateGraph for:
    - Parallel sub-task search (Send API)
    - Quality reflection loop (reflect -> revise -> reflect)
    - Native SSE streaming via astream_events
    """

    def __init__(self):
        self.chat_model = create_chat_model(config)
        self.graph = build_research_graph(self.chat_model)

    async def research(self, topic: str) -> AsyncGenerator[str, None]:
        """Execute deep research, yielding SSE-formatted events"""
        initial_state = {
            "query": topic,
            "sub_tasks": [],
            "current_task_index": 0,
            "draft_report": "",
            "critique": "",
            "final_report": "",
            "iterations": 0,
            "status": "starting",
            "error": None,
        }

        try:
            async for event in self.graph.astream_events(
                initial_state,
                version="v2",
                config={"recursion_limit": 25},
            ):
                kind = event["event"]
                name = event["name"]
                data = event.get("data", {})

                if kind == "on_chain_start":
                    if name == "decompose":
                        yield self._format_sse("status", "正在规划研究任务...", percentage=10)
                    elif name == "fan_out":
                        yield self._format_sse("status", "正在并行搜索...", percentage=20)
                    elif name == "search_sub_task":
                        task_idx = data.get("input", {}).get("current_task_index", 0)
                        sub_tasks = data.get("input", {}).get("sub_tasks", [])
                        if sub_tasks and task_idx < len(sub_tasks):
                            task_title = sub_tasks[task_idx].get("title", "")
                            yield self._format_sse(
                                "task_progress",
                                f"正在搜索：{task_title}",
                                task_id=task_idx + 1,
                            )
                    elif name == "summarize":
                        yield self._format_sse("status", "正在总结搜索结果...", percentage=50)
                    elif name == "generate_report":
                        yield self._format_sse("status", "正在生成报告...", percentage=75)
                    elif name == "reflect":
                        yield self._format_sse("status", "正在审查报告质量...", percentage=85)
                    elif name == "revise":
                        yield self._format_sse("status", "正在修改报告...", percentage=88)
                    elif name == "finalize":
                        yield self._format_sse("status", "正在完成报告...", percentage=95)

                elif kind == "on_chain_end":
                    if name == "decompose" and "output" in data:
                        tasks = data["output"].get("sub_tasks", [])
                        yield self._format_sse(
                            "tasks",
                            f"已规划 {len(tasks)} 个子任务",
                            data={"tasks": tasks},
                            percentage=15,
                        )
                    elif name == "search_sub_task" and "output" in data:
                        task_idx = data.get("input", {}).get("current_task_index", 0)
                        sub_tasks = data.get("output", {}).get("sub_tasks", [])
                        if sub_tasks and task_idx < len(sub_tasks):
                            task = sub_tasks[task_idx]
                            result_count = len(task.get("search_results", []))
                            yield self._format_sse(
                                "status",
                                f"任务 {task_idx + 1} 搜索完成，找到 {result_count} 条结果",
                                task_id=task_idx + 1,
                            )
                    elif name == "finalize" and "output" in data:
                        report = data["output"].get("final_report", "")
                        yield self._format_sse(
                            "report",
                            "研究完成",
                            data={"report": report},
                            percentage=100,
                            stage="completed",
                        )

        except Exception as e:
            logger.error(f"Research error: {e}", exc_info=True)
            yield self._format_sse("error", f"研究出错: {str(e)}")

    def run(self, topic: str) -> str:
        """Synchronous research (non-streaming)"""
        initial_state = {
            "query": topic,
            "sub_tasks": [],
            "current_task_index": 0,
            "draft_report": "",
            "critique": "",
            "final_report": "",
            "iterations": 0,
            "status": "starting",
            "error": None,
        }

        result = self.graph.invoke(
            initial_state,
            config={"recursion_limit": 25},
        )
        return result.get("final_report", "")

    def _format_sse(self, event_type: str, message: str = None, data: dict = None, **kwargs) -> str:
        """Format SSE event"""
        event_data = {"type": event_type, **(kwargs if kwargs else {})}
        if message:
            event_data["message"] = message
        if data:
            event_data["data"] = data
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"


# Backward compatibility alias
DeepResearchAgent = LangGraphAgent
