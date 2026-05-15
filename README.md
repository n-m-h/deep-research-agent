# 🔍 深度研究助手 (Deep Research Agent)

基于 [HelloAgents](https://github.com/datawhalechina/Hello-Agents) 框架构建的自动化深度研究智能体系统，能够自主规划、执行和总结研究任务，生成结构化的研究报告。

> **v3.0**: 新增 RAG 知识库功能！支持上传个人文档（PDF/TXT/MD/DOCX），研究时自动结合网络搜索与个人文档内容进行分析。

> **v3.1**: LangGraph + RAG 版设为默认！`USE_LANGGRAPH=true` 开箱即用。如需切回经典版，设 `USE_LANGGRAPH=false`。

## ✨ 特性

- **TODO 驱动的研究范式**：将复杂主题分解为可执行的子任务
- **多 LLM 自动切换**：支持配置多个 LLM 提供商，主 LLM 失败时自动切换备用
- **多源搜索集成**：支持 Tavily、DuckDuckGo 等搜索引擎，带超时保护
- **RAG 个人知识库**：上传 PDF/TXT/MD/DOCX 文档，研究时自动检索相关内容（仅 LangGraph 版）
- **SSE 流式输出**：实时展示研究进度和任务状态
- **并行搜索 (LangGraph)**：子任务级并行搜索，大幅提升研究速度
- **质量审查 (LangGraph)**：自动审查报告质量，支持最多 2 轮改进循环
- **结构化报告**：生成 Markdown 格式的研究报告，信息来源标注网络资源和个人文档
- **评估框架**：内置 RAG 检索质量评估工具，支持多策略 A/B 对比

## 🏗 项目结构

```
helloagents-deepresearch/
├── backend/                      # 后端服务
│   ├── src/
│   │   ├── main.py              # FastAPI 入口 + SSE 接口 + 文档管理 API
│   │   ├── agent.py             # DeepResearchAgent (原版)
│   │   ├── agent_langgraph.py   # LangGraphAgent (新版)
│   │   ├── config.py            # 多 LLM + RAG 配置管理
│   │   ├── models.py            # Pydantic 数据模型
│   │   ├── prompts.py           # Agent Prompt 模板（支持双来源标注）
│   │   ├── utils.py             # 公共工具函数（JSON 提取等）
│   │   ├── langgraph_llm.py    # LangChain LLM 包装器
│   │   ├── tool_aware_agent.py  # ToolAwareSimpleAgent 扩展
│   │   ├── graph/               # LangGraph 工作流
│   │   │   ├── __init__.py
│   │   │   ├── state.py         # ResearchState 定义
│   │   │   ├── nodes.py         # 图节点实现（集成 RAG 检索）
│   │   │   └── builder.py       # StateGraph 构建器
│   │   └── services/            # 服务层
│   │       ├── planner.py       # 任务规划服务
│   │       ├── summarizer.py    # 任务总结服务
│   │       ├── reporter.py      # 报告生成服务（批处理）
│   │       ├── search.py        # 多源搜索调度服务
│   │       ├── rag.py           # RAG 检索服务（混合搜索 + 重排序）
│   │       └── document_processor.py # 文档解析与分块引擎
│   ├── evaluation/              # RAG 评估框架
│   │   ├── run_evaluation.py    # 评估脚本（Precision/Recall/MRR）
│   │   └── test_queries.json    # 标准测试查询集
│   ├── scripts/
│   │   └── test_rag.py          # RAG 交互式测试脚本
│   ├── rag_storage/             # ChromaDB 持久化目录
│   ├── venv/                    # Python 虚拟环境
│   └── .env                     # 环境变量配置
│       .env.example             # 环境变量模板
│
├── frontend/                    # 前端界面
│   ├── index.html               # 独立 HTML 页面（含 RAG 管理面板）
│   └── vite.config.ts           # Vite 开发代理配置
│
├── start.sh                     # 一键启动脚本
└── README.md                    # 本文档
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+ (可选，用于前端开发)

### 安装与启动

#### 1. 配置环境变量

复制并编辑 `backend/.env` 文件：

```bash
# ==================== LLM 配置 (主) ====================
LLM_PROVIDER=siliconflow
LLM_API_KEY=your_api_key
LLM_MODEL_ID=Pro/MiniMaxAI/MiniMax-M2.5
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_TEMPERATURE=0.7
LLM_TIMEOUT=120

# ==================== 备用 LLM 1 ====================
LLM_PROVIDER_1=siliconflow
LLM_API_KEY_1=your_api_key_1
LLM_MODEL_1=deepseek-ai/DeepSeek-V3
LLM_BASE_URL_1=https://api.siliconflow.cn/v1

# ==================== 备用 LLM 2 ====================
LLM_PROVIDER_2=openai
LLM_API_KEY_2=your_api_key_2
LLM_MODEL_2=gpt-4
LLM_BASE_URL_2=https://api.openai.com/v1

# ==================== 搜索引擎配置 ====================
SEARCH_API=tavily
TAVILY_API_KEY=your_tavily_key

# ==================== 应用配置 ====================
WORKSPACE_DIR=./workspace
MAX_SEARCH_RESULTS=10
MAX_TOOL_ITERATIONS=3
HOST=0.0.0.0
PORT=8000
```

#### 2. 启动后端

```bash
cd helloagents-deepresearch/backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或: venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 启动（默认 LangGraph + RAG 版本）
python src/main.py

# 如需切回经典版（不含 RAG 和并行搜索）
# USE_LANGGRAPH=false python src/main.py
```

#### 3. 启动前端

```bash
cd helloagents-deepresearch/frontend

# 使用 Python 静态服务器（无需安装 Node.js）
python -m http.server 8080

# 或使用 Node.js 开发模式
# npm install
# npm run dev
```

### 访问

- **前端**：http://localhost:8080（静态服务器）或 http://localhost:5174（Vite 开发模式）
- **后端 API**：http://localhost:8000

## 📄 RAG 个人知识库

### 功能介绍

RAG（检索增强生成）功能允许你上传个人文档，在研究时系统会**同时检索网络信息和个人文档**，将两方面的信息融合到最终报告中。

### 上传文档

通过前端页面的「个人知识库」面板上传文档：

1. 打开 http://localhost:8080
2. 在搜索框下方找到「个人知识库」面板
3. 拖拽文件到上传区域，或点击选择文件
4. 支持格式：**PDF / TXT / MD / DOCX**

### 研究时使用

- 面板中的「研究中同时查询个人文档」开关控制是否启用 RAG
- 研究开始后，系统自动并行执行**网络搜索**和**个人文档检索**
- 最终报告中，信息来源会标注 `[网络]` 和 `[个人文档]`
- 参考文献分为「网络资源」和「个人文档」两类

### API 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `POST /documents/upload` | POST | 上传并索引文档 |
| `GET /documents` | GET | 列出已索引文档 |
| `DELETE /documents/{doc_id}` | DELETE | 删除文档索引 |
| `GET /rag/status` | GET | RAG 服务状态 |
| `GET /rag/search?query=xxx` | GET | 调试搜索 |

### RAG 技术实现

- **解析引擎**：`DocumentProcessor` 支持多格式文档解析（PDF/DOCX/MD/TXT），提取结构信息（标题层级、分节路径）
- **分块策略**：3 种策略可选（递归分块、标题感知分块、父子分块），通过 `RAG_CHUNK_STRATEGY` 切换
- **混合检索**：稠密向量检索（BGE embedding）+ BM25 稀疏检索，RRF 融合算法
- **重排序**：Cross-encoder 模型（bge-reranker-v2-m3）对候选结果重排序，提高精度
- **查询扩展**：LLM 生成同义查询变体，提高召回率

## ⚙️ 配置说明

### 版本切换

```bash
# true → LangGraph 版（并行搜索 + RAG + 质量审查，默认）
# false → Classic 版（串行执行，无 RAG）
USE_LANGGRAPH=true
```

### RAG 配置

```bash
# ==================== RAG 配置 ====================
RAG_ENABLED=true
RAG_CHUNK_STRATEGY=parent_child     # recursive / heading / parent_child
RAG_CHUNK_SIZE=500                  # 子块大小（字符数）
RAG_CHUNK_OVERLAP=75                # 重叠字符数
RAG_PARENT_CHUNK_SIZE=1500          # 父块大小（parent_child 策略）
RAG_TOP_K=5                         # 最终返回结果数
RAG_CANDIDATE_K=20                  # 重排序前候选数
RAG_USE_RERANK=true                 # 是否启用重排序
RAG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
RAG_RERANK_MODEL=BAAI/bge-reranker-v2-m3
RAG_HYBRID_WEIGHT_DENSE=0.6         # 稠密检索权重
RAG_HYBRID_WEIGHT_SPARSE=0.4        # 稀疏检索权重
```

### 多 LLM 自动切换

系统支持配置最多 10 个备用 LLM，当主 LLM 调用失败时自动切换：

```bash
# 主 LLM
LLM_PROVIDER=siliconflow
LLM_API_KEY=xxx
LLM_MODEL_ID=model-name
LLM_BASE_URL=https://api.example.com/v1

# 备用 LLM 1 (索引从 1 开始)
LLM_PROVIDER_1=openai
LLM_API_KEY_1=xxx
LLM_MODEL_1=gpt-4
LLM_BASE_URL_1=https://api.openai.com/v1

# 备用 LLM 2
LLM_PROVIDER_2=deepseek
LLM_API_KEY_2=xxx
LLM_MODEL_2=deepseek-chat
LLM_BASE_URL_2=https://api.deepseek.com/v1
```

### 支持的 LLM 提供商

| Provider | 说明 |
|----------|------|
| `siliconflow` | SiliconFlow API |
| `openai` | OpenAI API |
| `deepseek` | DeepSeek API |
| `qwen` | 通义千问 API |
| `custom` | 自定义 OpenAI 兼容 API |

### 搜索引擎配置

```bash
SEARCH_API=tavily          # tavily / duckduckgo
TAVILY_API_KEY=xxx         # Tavily API Key
SERPAPI_API_KEY=xxx        # SerpApi API Key (可选)
MAX_SEARCH_RESULTS=10      # 每次搜索最大结果数
```

## 🔌 API 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 首页 |
| `/health` | GET | 健康检查 |
| `/research` | POST | 同步研究（返回完整报告） |
| `/research/stream` | POST | SSE 流式研究 |
| `/documents/upload` | POST | 上传文档 |
| `/documents` | GET | 文档列表 |
| `/documents/{doc_id}` | DELETE | 删除文档 |
| `/rag/status` | GET | RAG 状态 |
| `/rag/search` | GET | RAG 搜索调试 |

### 使用示例

```bash
# 同步研究（带 RAG）
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "人工智能的发展历史", "use_rag": true}'

# 流式研究
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"topic": "大语言模型的应用场景", "use_rag": true}'

# 上传文档
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/document.pdf"
```

## 🧠 核心架构

### 三版本对比

| 特性 | 原版 (Classic) | LangGraph 版 | LangGraph + RAG 版 |
|------|----------------|--------------|-------------------|
| 任务执行 | 串行执行 | 并行执行 (Send API) | 并行执行 (Send API) |
| 网络搜索 | ✅ | ✅ | ✅ |
| 个人文档检索 | ❌ | ❌ | ✅ |
| 质量审查 | 无 | reflect → revise 循环 | reflect → revise 循环 |
| 状态管理 | SummaryState | ResearchState | ResearchState |
| 流式输出 | 手动 SSE | astream_events | astream_events |

### LangGraph 研究流程（含 RAG）

```
query → decompose → fan_out ──┬─→ search_1 (web + RAG) ─┐
                              ├─→ search_2 (web + RAG) ─┤  (并行)
                              ├─→ search_3 (web + RAG) ─┤
                              └─→ ...                   ┘
                                    ↓
                            summarize (双来源标注)
                                    ↓
                            generate_report
                            (参考文献分网络/个人文档两类)
                                    ↓
                          ┌─── reflect ────┐
                          │                │
               APPROVED   ▼         ▼         NEEDS_REVISION
            ─────────▶ finalize    revise ──▶ (loop)
```

### 多 Agent 协作

| Agent | 职责 | 输出 |
|-------|------|------|
| **TODO Planner** | 将主题分解为 3-5 个子任务 | JSON 任务列表 |
| **Task Summarizer** | 总结搜索结果 + 文档检索结果 | Markdown 总结（标注来源类型） |
| **Report Writer** | 整合所有总结，生成最终报告 | 结构化报告（双来源引用） |
| **Report Reflector** (LangGraph) | 审查报告质量，提出改进意见 | 审查报告 |
| **Report Reviser** (LangGraph) | 根据审查意见修改报告 | 改进后报告 |

### SSE 事件类型

| 事件类型 | 说明 |
|---------|------|
| `status` | 状态消息（进度、阶段） |
| `tasks` | 规划的子任务列表 |
| `task_progress` | 任务执行进度 |
| `task_summary` | 单个任务总结完成 |
| `report` | 最终报告（含 `stage: "completed"`） |
| `error` | 错误信息 |
| `completed` | 完成通知 |

## 🧪 RAG 评估

### 运行评估

```bash
cd backend
python evaluation/run_evaluation.py
```

输出示例：
```
🔍 RAG 评估 - 当前配置
============================================================
综合指标:
  Precision: 0.850
  Recall:    0.820
  F1 Score:  0.835
  MRR:       0.910

📊 策略对比
============================================================
策略                  Precision    Recall       F1           MRR
--------------------------------------------------------------------
recursive             0.720        0.680        0.699        0.810
heading               0.780        0.750        0.765        0.860
parent_child          0.850        0.820        0.835        0.910
```

### 交互式测试

```bash
cd backend
python scripts/test_rag.py status
python scripts/test_rag.py --file /path/to/doc.pdf upload
python scripts/test_rag.py --query "AI产品经理的职责" search
python scripts/test_rag.py compare
```

## 🔧 扩展开发

### 添加新的搜索引擎

编辑 `backend/src/services/search.py`：

```python
class SearchService:
    def _search_new_engine(self, query: str) -> List[dict]:
        # 实现新的搜索逻辑
        results = your_search_api(query)
        return self._format_results(results)
```

### 切换分块策略

通过环境变量切换：

```bash
RAG_CHUNK_STRATEGY=recursive       # 递归分块（基线）
RAG_CHUNK_STRATEGY=heading         # 标题感知分块（结构化文档）
RAG_CHUNK_STRATEGY=parent_child    # 父子分块（推荐，精度最高）
```

### 添加新的 Agent

1. 在 `backend/src/prompts.py` 中添加 Prompt 模板
2. 在 `backend/src/services/` 中创建服务类
3. 在 `backend/src/agent.py` 中集成

## 📝 示例输出

输入：`Datawhale 是一个什么样的组织？`

输出：

```markdown
# Datawhale是一个什么样的组织？

## 概述

本报告系统地研究了 Datawhale 这个开源组织...

## 1. 基本信息

Datawhale 是一个专注于数据科学与 AI 领域的开源组织，成立于 2018 年...

## 2. 核心项目

Datawhale 发布了多个高质量的开源教程，包括：
- 《机器学习开源教程》
- 《深度学习入门》
- ...

## 3. 社区文化

Datawhale 倡导"for the learner"理念，致力于降低学习门槛...

## 总结

通过本次研究，我们了解了 Datawhale 的组织定位、核心项目和社区文化...

## 参考文献

### 网络资源
[1] https://github.com/datawhalechina
[2] https://datawhale.club

### 个人文档
[AI产品经理知识手册.pdf] 相关背景分析
```

## 🔒 安全注意事项

- **不要提交 `.env` 文件**：包含敏感的 API 密钥
- **API 密钥保护**：确保 LLM 和搜索 API 密钥安全存储
- **生产环境**：建议使用环境变量或密钥管理服务
- **`.gitignore` 已配置**：`.env`、`rag_storage/`、`__pycache__/` 等已排除

## 📄 License

MIT License

## 👏 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) - 轻量级智能体框架
- [Tavily](https://tavily.com/) - AI 搜索引擎
- [ChromaDB](https://www.trychroma.com/) - 开源向量数据库
- [SiliconFlow](https://siliconflow.cn/) - LLM API + Embedding + Rerank 服务
- [DataWhale](https://datawhale.club/) - 开源学习社区
