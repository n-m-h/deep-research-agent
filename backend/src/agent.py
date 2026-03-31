"""
DeepResearchAgent - 深度研究智能体核心协调器
"""
import sys
import os
from typing import AsyncGenerator, Callable, Optional, List
from datetime import datetime
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "HelloAgents")))

from hello_agents import HelloAgentsLLM
from hello_agents.core.llm import MultiProviderLLM

from .config import config
from .models import SummaryState, TodoItem, ResearchEvent
from .services import PlanningService, SummarizationService, ReportingService, SearchService

logger = logging.getLogger(__name__)


class DeepResearchAgent:
    """深度研究智能体核心协调器
    
    负责调度三个专门的Agent完成深度研究任务：
    1. TODO Planner - 规划研究任务
    2. Task Summarizer - 总结搜索结果  
    3. Report Writer - 生成最终报告
    """

    def __init__(
        self,
        llm: Optional[HelloAgentsLLM] = None,
        event_callback: Optional[Callable[[ResearchEvent], None]] = None
    ):
        self.llm = llm or self._create_llm()
        self.event_callback = event_callback

        self.planner = PlanningService(self.llm, self._on_tool_call)
        self.summarizer = SummarizationService(self.llm, self._on_tool_call)
        self.reporter = ReportingService(self.llm, self._on_tool_call)
        self.search_service = SearchService()

    def _create_llm(self):
        """创建 LLM 客户端（支持多 Provider 自动切换）"""
        primary_llm = HelloAgentsLLM(
            model=config.llm_model_id,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            provider=config.llm_provider,
            temperature=config.llm_temperature,
            timeout=config.llm_timeout
        )
        
        backup_llms = []
        for i, llm_config in enumerate(config.llm_providers):
            backup_llm = HelloAgentsLLM(
                model=llm_config.model_id,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                provider=llm_config.provider,
                temperature=llm_config.temperature,
                timeout=llm_config.timeout
            )
            backup_llms.append((backup_llm, f"backup_{i+1}"))
            logger.info(f"✅ 备用 LLM {i+1}: {llm_config.provider} - {llm_config.model_id}")
        
        if backup_llms:
            logger.info(f"🔄 启用多 LLM 自动切换，主: {config.llm_model_id}, 备用: {len(backup_llms)} 个")
            return MultiProviderLLM(primary_llm, backup_llms)
        
        return primary_llm

    def _on_tool_call(self, call_info: dict):
        """工具调用监听器"""
        if self.event_callback:
            event = ResearchEvent(
                type="tool_call",
                message=f"Agent {call_info['agent_name']} 调用了工具 {call_info['tool_name']}",
                data=call_info
            )
            self.event_callback(event)

    def _emit_event(self, event_type: str, message: str = None, data: dict = None, **kwargs):
        """发送事件"""
        if self.event_callback:
            event = ResearchEvent(
                type=event_type,
                message=message,
                data=data,
                **kwargs
            )
            self.event_callback(event)

    async def research(self, topic: str) -> AsyncGenerator[str, None]:
        """执行深度研究，返回SSE格式的流式数据"""
        
        try:
            yield self._format_sse_event("status", "正在初始化研究任务...", percentage=0)
            
            state = SummaryState(research_topic=topic)

            yield self._format_sse_event("status", "正在规划研究任务...", percentage=10)
            # 任务规划
            todo_list = self.planner.plan_todo_list(state)
            
            yield self._format_sse_event(
                "tasks", 
                f"已规划 {len(todo_list)} 个子任务",
                data={"tasks": [task.model_dump() for task in todo_list]},
                percentage=15
            )

            task_summaries = []
            total_tasks = len(todo_list)
            # 逐一执行规划的子任务
            for idx, task in enumerate(todo_list, start=1):
                base_percentage = 15
                progress_per_task = 70
                task_percentage = base_percentage + (idx / total_tasks) * progress_per_task
                
                yield self._format_sse_event(
                    "status",
                    f"正在研究任务 {idx}/{total_tasks}：{task.title}",
                    percentage=task_percentage,
                    stage="executing"
                )

                yield self._format_sse_event(
                    "task_progress",
                    f"正在搜索：{task.query}",
                    task_id=task.id,
                    data={"task": task.model_dump()}
                )
                # 搜索
                search_results = self.search_service.search(task.query)
                # 处理无结果的情况
                if not search_results:
                    yield self._format_sse_event(
                        "warning",
                        f"未找到关于「{task.title}」的相关信息",
                        task_id=task.id
                    )
                    task.summary = "未找到相关信息"
                    task_summaries.append((task, "未找到相关信息", []))
                    continue

                yield self._format_sse_event(
                    "status",
                    f"正在总结搜索结果...",
                    percentage=task_percentage + 5
                )
                # 总结
                summary, source_urls = self.summarizer.summarize_task(task, search_results)
                task.summary = summary
                task.source_urls = source_urls

                task_summaries.append((task, summary, source_urls))

                yield self._format_sse_event(
                    "task_summary",
                    f"任务 {idx} 完成",
                    task_id=task.id,
                    data={
                        "task_id": task.id,
                        "summary": summary,
                        "source_urls": source_urls
                    },
                    percentage=task_percentage + 10
                )

            yield self._format_sse_event(
                "status",
                "正在生成最终报告...",
                percentage=90,
                stage="reporting"
            )
            
            # 生成完整报告
            report = self.reporter.generate_report(topic, task_summaries)

            yield self._format_sse_event(
                "report",
                "研究完成",
                data={"report": report},
                percentage=100,
                stage="completed"
            )

        except Exception as e:
            logger.error(f"研究过程出错: {e}")
            yield self._format_sse_event(
                "error",
                f"研究出错: {str(e)}",
                data={"error": str(e)}
            )

    def _format_sse_event(
        self,                  # 当前类的实例
        event_type: str,       # 事件类型，字符串格式
        message: str = None,   # 可选的消息内容，默认为None
        data: dict = None,    # 可选的数据字典，默认为None
        **kwargs             # 其他可选的关键字参数
    ) -> str:               # 返回格式化后的字符串
        """格式化SSE事件"""
        event_data = {                      # 构建事件主体
            "type": event_type,
            **(kwargs if kwargs else {}),     # 解包关键字参数
        }
        if message:
            event_data["message"] = message
        if data:
            event_data["data"] = data
            
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def run(self, topic: str) -> str:
        """同步运行研究（用于非流式场景），与reasearch方法本质相同，但是run方法不返回SSE格式的流式数据"""
        state = SummaryState(research_topic=topic)

        todo_list = self.planner.plan_todo_list(state)
        
        task_summaries = []
        for task in todo_list:
            search_results = self.search_service.search(task.query)
            
            if search_results:
                summary, source_urls = self.summarizer.summarize_task(task, search_results)
                task.summary = summary
                task.source_urls = source_urls
                task_summaries.append((task, summary, source_urls))

        report = self.reporter.generate_report(topic, task_summaries)
        
        return report
