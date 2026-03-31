"""
配置管理
"""
import os
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class SearchAPI(str, Enum):
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    PERPLEXITY = "perplexity"
    SEARXNG = "searxng"
    ADVANCED = "advanced"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    CUSTOM = "custom"
    SILICONFLOW = "siliconflow"


class LLMConfig(BaseModel):
    provider: str
    api_key: str
    model_id: str
    base_url: str
    temperature: float = 0.7
    timeout: int = 120


class Configuration(BaseModel):
    llm_provider: str = os.getenv("LLM_PROVIDER", "custom")
    llm_api_key: Optional[str] = os.getenv("LLM_API_KEY")
    llm_model_id: str = os.getenv("LLM_MODEL_ID", "gpt-3.5-turbo")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))

    llm_providers: List[LLMConfig] = []

    search_api: SearchAPI = SearchAPI(os.getenv("SEARCH_API", "tavily"))
    tavily_api_key: Optional[str] = os.getenv("TAVILY_API_KEY")
    serpapi_api_key: Optional[str] = os.getenv("SERPAPI_API_KEY")

    workspace_dir: str = os.getenv("WORKSPACE_DIR", "./workspace")
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "3"))

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    class Config:
        extra = "allow"

    def __init__(self, **data):
        super().__init__(**data)
        self._load_backup_llms()

    def _load_backup_llms(self):
        backup_llms = []
        for i in range(10):
            provider = os.getenv(f"LLM_PROVIDER_{i}")
            api_key = os.getenv(f"LLM_API_KEY_{i}")
            model_id = os.getenv(f"LLM_MODEL_{i}")
            base_url = os.getenv(f"LLM_BASE_URL_{i}")
            
            if provider and api_key and model_id and base_url:
                backup_llms.append(LLMConfig(
                    provider=provider,
                    api_key=api_key,
                    model_id=model_id,
                    base_url=base_url,
                    temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
                    timeout=int(os.getenv("LLM_TIMEOUT", "120"))
                ))
        
        self.llm_providers = backup_llms


config = Configuration()
