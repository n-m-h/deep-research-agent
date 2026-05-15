#!/usr/bin/env python3
import sys
import os

# 添加必要的路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir))
project_root = os.path.abspath(os.path.join(backend_dir, "..", ".."))

sys.path.insert(0, backend_dir)

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

# 初始化LLM（必须通过环境变量配置，见 .env.example）
required_vars = {
    "LLM_API_KEY": "API 密钥",
    "LLM_BASE_URL": "API 地址",
    "LLM_MODEL_ID": "模型 ID",
}
missing = [f"{k} ({v})" for k, v in required_vars.items() if not os.getenv(k)]
if missing:
    print(f"❌ 缺少必要环境变量: {', '.join(missing)}")
    print("   请复制 backend/.env.example 为 .env 并填写配置")
    sys.exit(1)

try:
    llm = HelloAgentsLLM(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model=os.environ["LLM_MODEL_ID"],
        temperature=0.7
    )
    print("✅ LLM 初始化成功")
except Exception as e:
    print(f"❌ LLM 初始化失败: {e}")
    sys.exit(1)
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