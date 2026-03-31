"""
ToolAwareSimpleAgent - 支持工具调用监听的Agent扩展
"""
import sys
import os
import time
import logging
from typing import Optional, Callable, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "HelloAgents")))

from hello_agents import SimpleAgent
from hello_agents import HelloAgentsLLM
from hello_agents.core.exceptions import LLMError

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 2


class RetryableLLM:
    """带重试机制的LLM包装器"""
    
    def __init__(self, llm: HelloAgentsLLM):
        self._llm = llm
    
    def _retry_on_error(self, func, *args, **kwargs):
        """重试机制 - 增强网络错误处理"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (LLMError, Exception) as e:
                last_error = e
                error_msg = str(e).lower()
                is_network_error = any(keyword in error_msg for keyword in [
                    'connection', 'timeout', 'network', 'ECONNREFUSED', 
                    'ETIMEDOUT', 'CERTIFICATE', 'ssl', 'certificate verify failed'
                ])
                
                if attempt < MAX_RETRIES - 1:
                    if is_network_error:
                        wait_time = RETRY_DELAY * (3 ** attempt)
                    else:
                        wait_time = RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"LLM调用失败 (尝试 {attempt + 1}/{MAX_RETRIES}), {wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"LLM调用最终失败: {e}")
        raise last_error
    
    def invoke(self, messages, **kwargs):
        return self._retry_on_error(self._llm.invoke, messages, **kwargs)
    
    def think(self, messages, **kwargs):
        return self._retry_on_error(self._llm.think, messages, **kwargs)
    
    def stream_invoke(self, messages, **kwargs):
        return self._retry_on_error(self._llm.stream_invoke, messages, **kwargs)
    
    def __getattr__(self, name):
        return getattr(self._llm, name)


class ToolAwareSimpleAgent(SimpleAgent):
    """支持工具调用监听的Agent
    
    继承自SimpleAgent，增加了tool_call_listener回调功能，
    可以在每次工具调用时通知监听器。
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        tool_registry=None,
        tool_call_listener: Optional[Callable[[dict], None]] = None,
        enable_tool_calling: bool = False,
        enable_retry: bool = True,
        **kwargs
    ):
        wrapped_llm = RetryableLLM(llm) if enable_retry else llm
        super().__init__(
            name=name,
            llm=wrapped_llm,
            system_prompt=system_prompt,
            tool_registry=tool_registry,
            enable_tool_calling=enable_tool_calling,
            **kwargs
        )
        self._tool_call_listener = tool_call_listener

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用，并通知监听器"""
        parsed_params = self._parse_parameters(parameters)
        
        result = super()._execute_tool_call(tool_name, parameters)
        
        if self._tool_call_listener:
            self._tool_call_listener({
                "agent_name": self.name,
                "tool_name": tool_name,
                "parsed_parameters": parsed_params,
                "result": result
            })
        
        return result

    def _parse_parameters(self, parameters: str) -> dict:
        """解析JSON参数字符串"""
        import json
        try:
            return json.loads(parameters)
        except json.JSONDecodeError:
            return {"raw": parameters}
