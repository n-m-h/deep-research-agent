"""
报告生成服务
"""
import logging
from typing import List, Callable, Optional, Tuple, Iterator

from ..models import TodoItem
from ..prompts import report_writer_instructions, report_merger_instructions
from ..tool_aware_agent import ToolAwareSimpleAgent

logger = logging.getLogger(__name__)

BATCH_SIZE = 2


class ReportingService:
    """报告生成服务 - 调用报告生成Agent，整合所有子任务的总结"""

    def __init__(
        self,
        llm,
        tool_call_listener: Optional[Callable] = None
    ):
        self._llm = llm
        self._tool_call_listener = tool_call_listener

        self._agent = ToolAwareSimpleAgent(
            name="Report Writer",
            system_prompt="你是一个报告撰写专家，擅长整合信息并生成结构化的报告。",
            llm=llm,
            tool_call_listener=tool_call_listener,
            enable_tool_calling=False
        )

    def generate_report(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> str:
        """生成最终报告

        Args:
            research_topic: 研究主题
            task_summaries: 子任务总结列表，每个元素是(任务, 总结, 来源URL列表)

        Returns:
            最终报告（Markdown格式）
        """
        total_tasks = len(task_summaries)
        logger.info(f"开始生成报告，共 {total_tasks} 个任务")

        if total_tasks <= BATCH_SIZE:
            logger.info(f"任务数量 <= {BATCH_SIZE}，直接生成报告")
            return self._generate_direct_report(research_topic, task_summaries)
        else:
            logger.info(f"任务数量 > {BATCH_SIZE}，分批处理")
            return self._generate_batched_report(research_topic, task_summaries)

    def _generate_direct_report(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> str:
        """直接生成报告（任务数量少时使用）"""
        formatted_summaries = self._format_summaries(task_summaries)

        prompt = report_writer_instructions.format(
            research_topic=research_topic,
            task_summaries=formatted_summaries,
        )

        logger.info("调用 LLM 生成完整报告...")
        report = self._agent.run(prompt)
        logger.info("报告生成完成")

        return report

    def _generate_batched_report(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> str:
        """分批生成报告（任务数量多时使用）"""
        batches = self._split_into_batches(task_summaries)
        logger.info(f"将 {len(task_summaries)} 个任务分成 {len(batches)} 批")

        partial_reports = []
        for idx, batch in enumerate(batches, start=1):
            logger.info(f"生成第 {idx}/{len(batches)} 批报告...")
            partial = self._generate_partial_report(research_topic, batch, idx, len(batches))
            partial_reports.append(partial)
            logger.info(f"第 {idx} 批报告完成")

        logger.info("合并所有部分报告...")
        final_report = self._merge_partial_reports(research_topic, partial_reports)
        logger.info("报告合并完成")

        return final_report

    def _split_into_batches(
        self,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> List[List[Tuple[TodoItem, str, List[str]]]]:
        """将任务摘要分成多个批次"""
        batches = []
        for i in range(0, len(task_summaries), BATCH_SIZE):
            batches.append(task_summaries[i:i + BATCH_SIZE])
        return batches

    def _generate_partial_report(
        self,
        research_topic: str,
        batch_summaries: List[Tuple[TodoItem, str, List[str]]],
        batch_num: int,
        total_batches: int
    ) -> str:
        """生成部分报告"""
        formatted_summaries = self._format_summaries(batch_summaries)

        batch_intro = f"""这是第 {batch_num}/{total_batches} 批任务报告。

请根据这批任务的总结，生成一份部分研究报告。
这批任务包含 {len(batch_summaries)} 个子任务。
"""

        prompt = report_writer_instructions.format(
            research_topic=f"{research_topic} (第 {batch_num}/{total_batches} 批)",
            task_summaries=batch_intro + formatted_summaries,
        )

        partial_report = self._agent.run(prompt)
        return partial_report

    def _merge_partial_reports(
        self,
        research_topic: str,
        partial_reports: List[str]
    ) -> str:
        """合并所有部分报告"""
        formatted_partials = "\n\n---\n\n".join(
            f"### 部分报告 {idx + 1}\n\n{report}"
            for idx, report in enumerate(partial_reports)
        )

        prompt = report_merger_instructions.format(
            research_topic=research_topic,
            partial_reports=formatted_partials,
        )

        merged_report = self._agent.run(prompt)
        return merged_report

    def generate_report_stream(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> Iterator[str]:
        """流式生成最终报告

        Args:
            research_topic: 研究主题
            task_summaries: 子任务总结列表

        Yields:
            报告的文本块
        """
        total_tasks = len(task_summaries)
        logger.info(f"开始流式生成报告，共 {total_tasks} 个任务")

        if total_tasks <= BATCH_SIZE:
            logger.info(f"任务数量 <= {BATCH_SIZE}，直接流式生成报告")
            yield from self._generate_direct_report_stream(research_topic, task_summaries)
        else:
            logger.info(f"任务数量 > {BATCH_SIZE}，分批处理后流式合并")
            yield from self._generate_batched_report_stream(research_topic, task_summaries)

    def _generate_direct_report_stream(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> Iterator[str]:
        """流式直接生成报告"""
        formatted_summaries = self._format_summaries(task_summaries)

        prompt = report_writer_instructions.format(
            research_topic=research_topic,
            task_summaries=formatted_summaries,
        )

        logger.info("流式调用 LLM 生成完整报告...")
        for chunk in self._agent.stream_run(prompt):
            yield chunk
        logger.info("报告流式生成完成")

    def _generate_batched_report_stream(
        self,
        research_topic: str,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> Iterator[str]:
        """分批生成报告，最后流式合并"""
        batches = self._split_into_batches(task_summaries)
        logger.info(f"将 {len(task_summaries)} 个任务分成 {len(batches)} 批")

        partial_reports = []
        for idx, batch in enumerate(batches, start=1):
            logger.info(f"生成第 {idx}/{len(batches)} 批报告...")
            partial = self._generate_partial_report(research_topic, batch, idx, len(batches))
            partial_reports.append(partial)
            logger.info(f"第 {idx} 批报告完成")

        logger.info("流式合并所有部分报告...")
        yield from self._merge_partial_reports_stream(research_topic, partial_reports)
        logger.info("报告合并完成")

    def _merge_partial_reports_stream(
        self,
        research_topic: str,
        partial_reports: List[str]
    ) -> Iterator[str]:
        """流式合并所有部分报告"""
        formatted_partials = "\n\n---\n\n".join(
            f"### 部分报告 {idx + 1}\n\n{report}"
            for idx, report in enumerate(partial_reports)
        )

        prompt = report_merger_instructions.format(
            research_topic=research_topic,
            partial_reports=formatted_partials,
        )

        for chunk in self._agent.stream_run(prompt):
            yield chunk

    def _format_summaries(
        self,
        task_summaries: List[Tuple[TodoItem, str, List[str]]]
    ) -> str:
        """格式化子任务总结"""
        formatted = []
        for idx, (task, summary, source_urls) in enumerate(task_summaries, start=1):
            formatted.append(
                f"## 任务{idx}：{task.title}\n\n"
                f"**意图**：{task.intent}\n\n"
                f"{summary}\n\n"
                f"**来源**：\n"
            )
            for url in source_urls:
                formatted.append(f"- {url}\n")
            formatted.append("\n")

        return "".join(formatted)
