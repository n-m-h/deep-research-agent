"""
FastAPI 后端入口
"""
import sys
import os
import json
import tempfile
import logging
import asyncio
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))

sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from hello_agents import HelloAgentsLLM

from src.config import config
from src.models import ResearchRequest
from src.services.rag import RAGService

# 版本切换: 通过环境变量 USE_LANGGRAPH 控制
# USE_LANGGRAPH=true  -> 使用 LangGraph 版本 (并行搜索 + 质量审查)
# USE_LANGGRAPH=false -> 使用原版 (串行执行)
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() == "true"

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

rag_service = RAGService()


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
            logger.info(f"开始研究 [{AGENT_VERSION}]: {request.topic}" + (f" [RAG启用]" if request.use_rag else ""))
            # 创建研究代理实例
            agent = ResearchAgent()

            if request.use_rag:
                yield f"data: {json.dumps({'type': 'status', 'message': f'📄 RAG已启用 ({rag_service.document_count}篇文档)', 'percentage': 0})}\n\n"
                await asyncio.sleep(0)
            
            # 异步迭代研究代理的研究结果
            if USE_LANGGRAPH:
                async for event in agent.research(request.topic, use_rag=request.use_rag):
                    logger.info(f"SSE事件: {event[:100]}...")
                    yield event
                    await asyncio.sleep(0)
            else:
                async for event in agent.research(request.topic):
                    logger.info(f"SSE事件: {event[:100]}...")
                    yield event
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
        if USE_LANGGRAPH:
            report = agent.run(request.topic, use_rag=request.use_rag)
        else:
            report = agent.run(request.topic)
        return {"status": "success", "report": report, "agent": AGENT_VERSION, "use_rag": request.use_rag}
    except Exception as e:
        logger.error(f"研究出错: {e}")
        return {"status": "error", "message": str(e)}


# ── Document Management API ──────────────────────────────────────────

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a document"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf", ".txt", ".md", ".docx"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: .pdf, .txt, .md, .docx")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = rag_service.index_document(tmp_path)
        os.unlink(tmp_path)

        return {"status": "success", "document": result}
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List all indexed documents"""
    docs = rag_service.list_documents()
    return {"documents": docs, "total": len(docs)}


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete an indexed document"""
    success = rag_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"status": "success", "message": f"Document {doc_id} deleted"}


@app.get("/rag/status")
async def rag_status():
    """Get RAG service status"""
    return {
        "enabled": config.rag_enabled,
        "document_count": rag_service.document_count,
        "strategy": config.rag_chunk_strategy,
        "use_rerank": config.rag_use_rerank,
        "embedding_model": config.rag_embedding_model,
        "rerank_model": config.rag_rerank_model,
    }


@app.get("/rag/search")
async def rag_search(query: str, top_k: int = 5):
    """Debug: search RAG index directly"""
    if not rag_service.has_documents:
        return {"results": [], "total_documents": 0}
    result = rag_service.search_debug(query, top_k)
    return result


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动深度研究助手 API ({AGENT_VERSION})...")
    print(f"📍 地址: http://{config.host}:{config.port}")
    print(f"🔧 USE_LANGGRAPH={USE_LANGGRAPH}")
    uvicorn.run(app, host=config.host, port=config.port)
