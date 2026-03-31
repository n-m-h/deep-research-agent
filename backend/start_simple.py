#!/usr/bin/env python3
import sys
import os

# 添加必要的路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir))
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

# 简化的配置
class Config:
    host = "0.0.0.0"
    port = 8000

config = Config()

# 初始化LLM
try:
    llm = HelloAgentsLLM(
        api_key=os.getenv("LLM_API_KEY", "sk-dIMTF6o6KFkhIZlU0849Ff6dD8214c1a88415aAf88266cA9"),
        base_url=os.getenv("LLM_BASE_URL", "https://aihubmix.com/v1"),
        model=os.getenv("LLM_MODEL_ID", "coding-glm-5-free"),
        temperature=0.7
    )
    print("✅ LLM 初始化成功")
except Exception as e:
    print(f"❌ LLM 初始化失败: {e}")
    sys.exit(1)

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

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动简化版深度研究助手 API...")
    print(f"📍 地址: http://{config.host}:{config.port}")
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")