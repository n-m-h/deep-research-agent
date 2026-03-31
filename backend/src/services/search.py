"""
搜索调度服务 - 多源并行搜索
"""
import os
import sys
import logging
import asyncio
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "HelloAgents")))

from ..config import config

logger = logging.getLogger(__name__)


class SearchService:
    """搜索调度服务 - 多源并行搜索，返回更全面的结果"""

    def __init__(self, backend: str = None):
        self.backend = backend or config.search_api.value
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.serpapi_key = os.getenv("SERPAPI_API_KEY")
        self.bing_key = os.getenv("BING_API_KEY")
        self.max_workers = 3
        self._init_clients()

    def _init_clients(self):
        """初始化搜索客户端"""
        self.tavily_client = None
        self.ddg_available = False
        self.bing_client = None

        if self.tavily_key:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.tavily_key)
                print("✅ Tavily 搜索源已启用")
            except ImportError:
                print("⚠️ Tavily 库未安装")
            except Exception as e:
                print(f"⚠️ Tavily 初始化失败: {e}")

        try:
            from ddgs import DDGS
            self.ddg_client = DDGS()
            self.ddg_available = True
            print("✅ DuckDuckGo 搜索源已启用")
        except ImportError:
            try:
                from duckduckgo_search import DDGS
                self.ddg_client = DDGS()
                self.ddg_available = True
                print("✅ DuckDuckGo 搜索源已启用 (旧版本)")
            except ImportError:
                print("⚠️ DuckDuckGo 库未安装 (pip install ddgs)")
        except Exception as e:
            print(f"⚠️ DuckDuckGo 初始化失败: {e}")

        if self.bing_key:
            try:
                self.bing_client = True
                print("✅ Bing 搜索源已启用")
            except Exception as e:
                print(f"⚠️ Bing 初始化失败: {e}")

        print(f"✅ SearchService 初始化成功，最大并行数: 3")

    def search(
        self,
        query: str,
        max_results: int = None
    ) -> List[dict]:
        """执行搜索 - 优先使用 Tavily，快速失败

        Args:
            query: 搜索查询
            max_results: 最大结果数量

        Returns:
            搜索结果列表
        """
        max_results = max_results or config.max_search_results
        
        all_results = []
        
        results = self._search_with_tavily(query, max_results)
        if results:
            all_results.extend(results)
            logger.info(f"搜索成功：{query}，返回{len(all_results)}个结果")
        else:
            logger.warning(f"搜索无结果：{query}")

        if all_results:
            all_results = self._deduplicate_sources(all_results)
            all_results = self._limit_source_tokens(all_results)

        return all_results[:max_results]

    def search_parallel(
        self,
        queries: List[str],
        max_results_per_query: int = 5
    ) -> List[dict]:
        """并行执行多个搜索查询

        Args:
            queries: 搜索查询列表
            max_results_per_query: 每个查询的最大结果数

        Returns:
            合并后的搜索结果列表
        """
        all_results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_query = {
                executor.submit(self.search, query, max_results_per_query): query
                for query in queries
            }
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.info(f"查询 '{query}' 完成，获取 {len(results)} 个结果")
                except Exception as e:
                    logger.error(f"查询 '{query}' 失败: {e}")
        
        all_results = self._deduplicate_sources(all_results)
        return all_results

    def _search_with_tavily(self, query: str, max_results: int) -> List[dict]:
        """使用 Tavily 搜索 - 带超时控制"""
        if not self.tavily_client:
            return []
            
        try:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Tavily 搜索超时")
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(8)
            
            response = self.tavily_client.search(
                query=query,
                search_depth="basic",
                include_answer=True,
                max_results=max_results
            )
            
            signal.alarm(0)
            
            results = []
            
            if response.get('answer'):
                results.append({
                    "title": f"AI摘要: {query}",
                    "url": "",
                    "snippet": response['answer'],
                    "source": "tavily",
                    "is_answer": True
                })
            
            for item in response.get('results', []):
                results.append({
                    "title": item.get('title', ''),
                    "url": item.get('url', ''),
                    "snippet": item.get('content', ''),
                    "source": "tavily",
                    "score": item.get('score', 0)
                })
            
            if results:
                logger.info(f"Tavily 搜索成功：{query}，返回{len(results)}个结果")
            return results
        except TimeoutError:
            logger.error(f"Tavily 搜索超时：{query}")
            return []
        except Exception as e:
            logger.error(f"Tavily 搜索失败：{e}")
            return []

    def _search_with_duckduckgo(self, query: str, max_results: int) -> List[dict]:
        """使用 DuckDuckGo 搜索 - 带超时控制"""
        if not self.ddg_available:
            return []
            
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("DuckDuckGo 搜索超时")
        
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)
            
            results = []
            for r in self.ddg_client.text(query, max_results=max_results):
                results.append({
                    "title": r.get('title', ''),
                    "url": r.get('href', ''),
                    "snippet": r.get('body', ''),
                    "source": "duckduckgo"
                })
            
            signal.alarm(0)
                
            if results:
                logger.info(f"DuckDuckGo 搜索成功：{query}，返回{len(results)}个结果")
            return results
        except TimeoutError:
            logger.warning(f"DuckDuckGo 搜索超时，跳过")
            return []
        except Exception as e:
            logger.warning(f"DuckDuckGo 搜索失败：{e}")
            return []

    def _search_with_bing(self, query: str, max_results: int) -> List[dict]:
        """使用 Bing 搜索"""
        if not self.bing_key:
            return []
            
        try:
            endpoint = "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                "Ocp-Apim-Subscription-Key": self.bing_key
            }
            params = {
                "q": query,
                "count": max_results,
                "mkt": "zh-CN"
            }
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(endpoint, headers=headers, params=params)
                
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get("webPages", {}).get("value", [])[:max_results]:
                    results.append({
                        "title": item.get("name", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "bing"
                    })
                
                if results:
                    logger.info(f"Bing 搜索成功：{query}，返回{len(results)}个结果")
                return results
        except Exception as e:
            logger.error(f"Bing 搜索失败：{e}")
        return []

    def _deduplicate_sources(self, sources: List[dict]) -> List[dict]:
        """去除重复的URL"""
        seen_urls = set()
        unique_sources = []

        for source in sources:
            url = source.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(source)
            elif not url and source.get("is_answer"):
                unique_sources.append(source)

        return unique_sources

    def _limit_source_tokens(
        self,
        sources: List[dict],
        max_tokens_per_source: int = 2000
    ) -> List[dict]:
        """限制每个来源的Token数量"""
        limited_sources = []

        for source in sources:
            snippet = source.get("snippet", "")
            max_chars = max_tokens_per_source * 4

            if len(snippet) > max_chars:
                snippet = snippet[:max_chars] + "..."

            limited_sources.append({
                **source,
                "snippet": snippet
            })

        return limited_sources
