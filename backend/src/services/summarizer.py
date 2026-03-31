"""
任务总结服务
"""
from typing import List, Callable, Optional, Tuple

from ..models import TodoItem
from ..prompts import task_summarizer_instructions
from ..tool_aware_agent import ToolAwareSimpleAgent


class SummarizationService:
    """任务总结服务 - 调用任务总结Agent，总结搜索结果"""

    def __init__(
        self,
        llm,
        tool_call_listener: Optional[Callable] = None
    ):
        self._llm = llm
        self._tool_call_listener = tool_call_listener

        self._agent = ToolAwareSimpleAgent(
            name="Task Summarizer",
            system_prompt="你是一个任务总结专家，擅长从搜索结果中提取关键信息。",
            llm=llm,
            tool_call_listener=tool_call_listener,
            enable_tool_calling=False
        )

    def summarize_task(
        self,
        task: TodoItem,
        search_results: List[dict]
    ) -> Tuple[str, List[str]]:
        """总结任务

        Args:
            task: 任务信息
            search_results: 搜索结果列表

        Returns:
            (总结文本, 来源URL列表)
        """
        formatted_sources = self._format_sources(search_results)

        prompt = task_summarizer_instructions.format(
            task_title=task.title,
            task_intent=task.intent,
            task_query=task.query,
            search_results=formatted_sources,
        )

        summary = self._agent.run(prompt)

        source_urls = [result["url"] for result in search_results]

        return summary, source_urls

    def _format_sources(self, search_results: List[dict]) -> str:
        """格式化搜索结果"""
        formatted = []
        for idx, result in enumerate(search_results, start=1):
            formatted.append(
                f"[{idx}] {result.get('title', 'Unknown')}\n"
                f"URL: {result.get('url', '')}\n"
                f"摘要: {result.get('snippet', '')}\n"
            )
        return "\n".join(formatted)
