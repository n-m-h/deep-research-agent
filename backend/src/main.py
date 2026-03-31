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
from src.agent import DeepResearchAgent
from src.models import ResearchRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="深度研究助手 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "深度研究助手 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """SSE 流式研究接口"""
    
    async def generate():
        try:
            logger.info(f"开始研究: {request.topic}")
            agent = DeepResearchAgent()
            
            async for event in agent.research(request.topic):
                logger.info(f"SSE事件: {event[:100]}...")
                yield event
                await asyncio.sleep(0)
                
        except Exception as e:
            logger.error(f"研究出错: {e}")
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
        agent = DeepResearchAgent()
        report = agent.run(request.topic)
        return {"status": "success", "report": report}
    except Exception as e:
        logger.error(f"研究出错: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动深度研究助手 API...")
    print(f"📍 地址: http://{config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port)
