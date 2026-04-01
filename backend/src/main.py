"""
FastAPI 后端入口
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))
helloagents_root = project_root

sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(helloagents_root, "HelloAgents"))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import asyncio

from hello_agents import HelloAgentsLLM

from src.config import config
from src.models import ResearchRequest

# 版本切换: 通过环境变量 USE_LANGGRAPH 控制
# USE_LANGGRAPH=true  -> 使用 LangGraph 版本 (并行搜索 + 质量审查)
# USE_LANGGRAPH=false -> 使用原版 (串行执行)
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").lower() == "true"

if USE_LANGGRAPH:
    from src.agent_langgraph import LangGraphAgent as ResearchAgent
    AGENT_VERSION = "LangGraph"
else:
    from src.agent import DeepResearchAgent as ResearchAgent
    AGENT_VERSION = "Classic"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="深度研究助手 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": f"深度研究助手 API ({AGENT_VERSION})",
        "version": "2.0.0",
        "agent": AGENT_VERSION,
        "langgraph_enabled": USE_LANGGRAPH,
    }


@app.get("/health")
# 这是一个异步函数，用于检查服务的健康状态
async def health():
    # 返回一个包含健康状态的字典，状态值为"healthy"
    return {"status": "healthy"}


@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """SSE 流式研究接口"""
    
    async def generate():
        """
        异步生成研究结果的生成器函数
        通过ResearchAgent进行异步研究，并通过Server-Sent Events(SSE)流式返回结果
        """
        try:
            # 记录开始研究的日志信息
            logger.info(f"开始研究 [{AGENT_VERSION}]: {request.topic}")
            # 创建研究代理实例
            agent = ResearchAgent()
            
            # 异步迭代研究代理的研究结果
            async for event in agent.research(request.topic):
                # 记录SSE事件的日志（只显示前100个字符）
                logger.info(f"SSE事件: {event[:100]}...")
                # 生成事件结果
                yield event
                # 让出控制权，允许其他协程运行
                await asyncio.sleep(0)
                
        except Exception as e:
            # 记录研究过程中的错误日志
            logger.error(f"研究出错: {e}")
            # 生成错误类型的SSE事件
            yield f"data: {{'type': 'error', 'message': '{str(e)}'}}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/research")
async def research(request: ResearchRequest):
    """同步研究接口（返回完整报告）"""
    try:
        agent = ResearchAgent()
        report = agent.run(request.topic)
        return {"status": "success", "report": report, "agent": AGENT_VERSION}
    except Exception as e:
        logger.error(f"研究出错: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动深度研究助手 API ({AGENT_VERSION})...")
    print(f"📍 地址: http://{config.host}:{config.port}")
    print(f"🔧 USE_LANGGRAPH={USE_LANGGRAPH}")
    uvicorn.run(app, host=config.host, port=config.port)
