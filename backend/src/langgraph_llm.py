"""
LangGraph-compatible LLM wrapper for HelloAgents MultiProviderLLM
Wraps HelloAgentsLLM as a LangChain BaseChatModel
"""
import sys
import os
from typing import List, Optional, Any, Iterator

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "HelloAgents")))

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from hello_agents import HelloAgentsLLM
from hello_agents.core.llm import MultiProviderLLM


def _to_openai_messages(messages: List[BaseMessage]) -> List[dict]:
    """Convert LangChain messages to OpenAI format"""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
        else:
            result.append({"role": "user", "content": str(msg.content)})
    return result


class HelloAgentsChatModel(BaseChatModel):
    """Wrap HelloAgentsLLM / MultiProviderLLM as LangChain BaseChatModel"""

    _llm: Any = None

    def __init__(self, llm, **kwargs):
        super().__init__(**kwargs)
        self._llm = llm

    @property
    def _llm_type(self) -> str:
        """返回LLM类型的字符串表示
        Returns:
            str: 返回"hello_agents"，表示这是一个hello_agents类型的LLM实现
        """
        return "hello_agents"

    def _generate(
        self,
        messages: List[BaseMessage],  # 输入的消息列表，包含对话历史
        stop: Optional[List[str]] = None,  # 可选的停止词列表，用于控制生成停止的条件
        run_manager: Any = None,  # 可选的运行管理器，用于跟踪和监控生成过程
        **kwargs: Any,  # 其他额外的关键字参数
    ) -> ChatResult:  # 返回聊天结果对象
        openai_msgs = _to_openai_messages(messages)  # 将输入的消息转换为OpenAI API兼容的消息格式
        response = self._llm.invoke(openai_msgs, **kwargs)  # 调用底层语言模型生成回复
        return ChatResult(  # 构建并返回聊天结果
            generations=[ChatGeneration(message=AIMessage(content=response))]  # 将模型响应封装为聊天生成结果
        )

    def _stream(
        self,
        messages: List[BaseMessage],  # 消息列表，包含对话历史
        stop: Optional[List[str]] = None,  # 可选的停止词列表
        run_manager: Any = None,  # 运行管理器，用于跟踪和控制运行过程
        **kwargs: Any,  # 其他可选参数
    ) -> Iterator[ChatGeneration]:  # 返回一个聊天生成结果的迭代器
        openai_msgs = _to_openai_messages(messages)  # 将消息转换为OpenAI格式
        for chunk in self._stream_with_fallback(openai_msgs, **kwargs):
            yield ChatGeneration(message=AIMessage(content=chunk))

    def _stream_with_fallback(self, messages: List[dict], **kwargs) -> Iterator[str]:
        """Stream with manual fallback for MultiProviderLLM (think() has no built-in fallback)"""
        from hello_agents.core.llm import MultiProviderLLM

        if isinstance(self._llm, MultiProviderLLM):
            tried = 0
            max_tries = len(self._llm.all_llms)
            while tried < max_tries:
                llm, name = self._llm.all_llms[self._llm.current_index]
                try:
                    for chunk in llm.think(messages, **kwargs):
                        yield chunk
                    return
                except Exception as e:
                    logger.warning(f"Stream LLM [{name}] failed: {e}, switching...")
                    self._llm._switch_to_next()
                    tried += 1
            raise LLMError("所有 LLM 提供商流式调用都失败")
        else:
            for chunk in self._llm.think(messages, **kwargs):
                yield chunk


def create_chat_model(config) -> HelloAgentsChatModel:
    """Create a LangGraph-compatible chat model from config"""
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

    if backup_llms:
        llm = MultiProviderLLM(primary_llm, backup_llms)
    else:
        llm = primary_llm

    return HelloAgentsChatModel(llm=llm)
