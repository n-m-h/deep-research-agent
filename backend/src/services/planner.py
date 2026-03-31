"""
任务规划服务
"""
import re
import json
from typing import List, Callable, Optional
from datetime import datetime

from ..models import TodoItem, SummaryState
from ..prompts import todo_planner_instructions
from ..tool_aware_agent import ToolAwareSimpleAgent


class PlanningService:
    """任务规划服务 - 调用研究规划Agent，将研究主题分解为子任务"""

    def __init__(
        self,
        llm,
        tool_call_listener: Optional[Callable] = None
    ):
        self._llm = llm
        self._tool_call_listener = tool_call_listener

        self._agent = ToolAwareSimpleAgent(
            name="TODO Planner",
            system_prompt="你是一个研究规划专家，擅长将复杂的研究主题分解为清晰的子任务。",
            llm=llm,
            tool_call_listener=tool_call_listener,
            enable_tool_calling=False
        )

    def plan_todo_list(self, state: SummaryState) -> List[TodoItem]:
        """规划TODO列表

        该方法根据研究状态生成一个待办事项列表，每个事项包含标题、意图和查询信息。
        Args:
            state: 研究状态，包含研究主题

        Returns:
            子任务列表
        """
        # 使用todo_planner_instructions模板格式化提示信息
        # 包含当前日期和研究主题
        prompt = todo_planner_instructions.format(
            current_date=self._get_current_date(),  # 获取当前日期
            research_topic=state.research_topic,    # 获取研究主题
        )

        # 运行AI代理生成响应
        response = self._agent.run(prompt)

        # 从响应中提取任务信息
        tasks_payload = self._extract_tasks(response)

        # 创建待办事项列表
        todo_items = []
        # 遍历提取的任务信息
        for idx, item in enumerate(tasks_payload, start=1):
            # 检查任务是否包含所有必需字段
            if not all(key in item for key in ["title", "intent", "query"]):
                raise ValueError(f"任务{idx}缺少必需字段")

            # 创建TodoItem对象并添加到列表
            task = TodoItem(
                id=idx,          # 任务ID      # 任务标题
                title=item["title"],
                intent=item["intent"],    # 任务意图
                query=item["query"],      # 查询信息
            )
            todo_items.append(task)

        return todo_items  # 返回完成的待办事项列表

    def _get_current_date(self) -> str:
        """获取当前日期"""
        return datetime.now().strftime("%Y年%m月%d日")

    def _extract_tasks(self, response: str) -> List[dict]:
        """从Agent响应中提取JSON"""
        response = response.strip()
        
        response = re.sub(r'^```json\s*', '', response)
        response = re.sub(r'^```\s*', '', response)
        response = re.sub(r'\s*```$', '', response)
        
        response = response.replace('"', '"').replace('"', '"')
        response = response.replace(''', "'").replace(''', "'")
        
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                pass

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if isinstance(data, dict) and "tasks" in data:
                    return data["tasks"]
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从响应中提取JSON: {response[:300]}")
