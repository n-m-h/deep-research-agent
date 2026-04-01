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
        return "hello_agents"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        openai_msgs = _to_openai_messages(messages)
        response = self._llm.invoke(openai_msgs, **kwargs)
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=response))]
        )

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        openai_msgs = _to_openai_messages(messages)
        for chunk in self._llm.think(openai_msgs, **kwargs):
            yield ChatGeneration(message=AIMessage(content=chunk))


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
