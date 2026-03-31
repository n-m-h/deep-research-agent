# 🔍 深度研究助手 (Deep Research Agent)

基于 [HelloAgents](https://github.com/datawhalechina/Hello-Agents) 框架构建的自动化深度研究智能体系统，能够自主规划、执行和总结研究任务，生成结构化的研究报告。

## ✨ 特性

- **TODO 驱动的研究范式**：将复杂主题分解为可执行的子任务
- **多 LLM 自动切换**：支持配置多个 LLM 提供商，主 LLM 失败时自动切换备用
- **多源搜索集成**：支持 Tavily、DuckDuckGo 等搜索引擎，带超时保护
- **Vue 3 现代前端**：基于 Vue 3 + TypeScript + Vite 构建的响应式界面
- **SSE 流式输出**：实时展示研究进度和任务状态
- **批处理报告生成**：大任务量时自动分批处理，提高稳定性
- **结构化报告**：生成 Markdown 格式的研究报告，包含来源引用

## 🏗 项目结构

```
helloagents-deepresearch/
├── backend/                      # 后端服务
│   ├── src/
│   │   ├── main.py              # FastAPI 入口 + SSE 接口
│   │   ├── agent.py             # DeepResearchAgent 核心协调器
│   │   ├── config.py            # 多 LLM 配置管理
│   │   ├── models.py            # Pydantic 数据模型
│   │   ├── prompts.py           # Agent Prompt 模板
│   │   ├── tool_aware_agent.py  # ToolAwareSimpleAgent 扩展
│   │   └── services/            # 服务层
│   │       ├── planner.py       # 任务规划服务
│   │       ├── summarizer.py    # 任务总结服务
│   │       ├── reporter.py      # 报告生成服务（批处理）
│   │       └── search.py        # 多源搜索调度服务
│   ├── venv/                    # Python 虚拟环境
│   └── .env                     # 环境变量配置
│
├── frontend/                     # Vue 3 前端
│   ├── src/
│   │   ├── App.vue              # 主应用组件
│   │   ├── main.ts              # 入口文件
│   │   ├── components/
│   │   │   └── ResearchModal.vue # 研究模态框
│   │   └── composables/
│   │       └── useResearch.ts   # SSE 流式处理
│   ├── package.json
│   └── vite.config.ts
│
├── start.sh                     # 一键启动脚本
└── README.md                    # 本文档
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+ (用于前端开发)

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

# 启动服务
python src/main.py
```

#### 3. 启动前端

```bash
cd helloagents-deepresearch/frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 访问

- 前端：http://localhost:5174
- 后端 API：http://localhost:8000

## ⚙️ 配置说明

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

### 使用示例

```bash
# 同步研究
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "人工智能的发展历史"}'

# 流式研究
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"topic": "Datawhale是什么组织"}'
```

## 🧠 核心架构

### 1. TODO 驱动的研究流程

```
用户输入 → 规划阶段 → 执行阶段 × N → 报告阶段 → 最终报告
               ↓           ↓              ↓
           子任务列表   搜索+总结      Markdown报告
```

### 2. 多 Agent 协作

| Agent | 职责 | 输出 |
|-------|------|------|
| **TODO Planner** | 将主题分解为 3-5 个子任务 | JSON 任务列表 |
| **Task Summarizer** | 总结搜索结果，提取关键信息 | Markdown 总结 |
| **Report Writer** | 整合所有总结，生成最终报告 | 结构化报告 |

### 3. SSE 事件类型

| 事件类型 | 说明 |
|---------|------|
| `status` | 状态消息（进度、阶段） |
| `tasks` | 规划的子任务列表 |
| `task_progress` | 任务执行进度 |
| `task_summary` | 单个任务总结完成 |
| `report` | 最终报告（含 `stage: "completed"`） |
| `error` | 错误信息 |
| `completed` | 完成通知 |

### 4. 批处理报告生成

当任务数量 > 2 时，系统自动分批处理：

1. 将 N 个任务分成若干批（每批 2 个）
2. 并行生成各批的部分报告
3. 最后合并所有部分报告为完整报告

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

### 添加新的 Agent

1. 在 `backend/src/prompts.py` 中添加 Prompt 模板
2. 在 `backend/src/services/` 中创建服务类
3. 在 `backend/src/agent.py` 中集成

### 修改前端界面

前端使用 Vue 3 + TypeScript，主要文件：

- `src/App.vue` - 主页面
- `src/components/ResearchModal.vue` - 研究结果模态框
- `src/composables/useResearch.ts` - SSE 流式处理逻辑

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

[1] https://github.com/datawhalechina
[2] https://datawhale.club
...
```

## 🔒 安全注意事项

- **不要提交 `.env` 文件**：包含敏感的 API 密钥
- **API 密钥保护**：确保 LLM 和搜索 API 密钥安全存储
- **生产环境**：建议使用环境变量或密钥管理服务

## 📄 License

MIT License

## 👏 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) - 轻量级智能体框架
- [Tavily](https://tavily.com/) - AI 搜索引擎
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [DataWhale](https://datawhale.club/) - 开源学习社区
