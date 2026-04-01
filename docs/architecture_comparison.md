# 原版 vs LangGraph 版 对比详解

## 一、架构对比

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              原版 (Classic) 架构                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  DeepResearchAgent                                                                   │
│    ├── __init__()                                                                    │
│    │     ├── self.llm = HelloAgentsLLM / MultiProviderLLM                            │
│    │     ├── self.planner = PlanningService(self.llm)                                │
│    │     ├── self.summarizer = SummarizationService(self.llm)                        │
│    │     ├── self.reporter = ReportingService(self.llm)                              │
│    │     └── self.search_service = SearchService()                                   │
│    │                                                                                 │
│    └── research(topic)                                                               │
│          │                                                                           │
│          ├── 1. state = SummaryState(research_topic=topic)                           │
│          ├── 2. todo_list = self.planner.plan_todo_list(state)                       │
│          │                                                                           │
│          ├── 3. for task in todo_list:  ← 串行执行                                    │
│          │     ├── search_results = self.search_service.search(task.query)           │
│          │     └── summary, urls = self.summarizer.summarize_task(task, results)     │
│          │                                                                           │
│          └── 4. report = self.reporter.generate_report(topic, task_summaries)        │
│                                                                                      │
│  特点：                                                                              │
│  - 手动管理状态 (SummaryState)                                                        │
│  - 子任务串行执行 (for loop)                                                          │
│  - 无质量审查环节                                                                     │
│  - 手动 SSE 事件格式化                                                                │
│  - 批处理报告生成 (reporter.py 内部逻辑)                                              │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            LangGraph 版 架构                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  LangGraphAgent                                                                      │
│    ├── __init__()                                                                    │
│    │     ├── self.chat_model = create_chat_model(config)                             │
│    │     │     └── HelloAgentsChatModel (包装 HelloAgentsLLM → LangChain)            │
│    │     └── self.graph = build_research_graph(self.chat_model)                      │
│    │           └── StateGraph(ResearchState) 编译后的图                               │
│    │                                                                                 │
│    └── research(topic)                                                               │
│          │                                                                           │
│          └── graph.astream_events(initial_state)  ← LangGraph 执行引擎               │
│                │                                                                     │
│                └── 自动按图定义执行节点，触发 astream_events 回调                     │
│                                                                                      │
│  特点：                                                                              │
│  - 统一状态管理 (ResearchState TypedDict)                                             │
│  - 子任务并行执行 (Send API)                                                          │
│  - 质量审查循环 (reflect → revise → reflect)                                          │
│  - 原生 SSE 支持 (astream_events)                                                     │
│  - 图结构清晰，节点职责单一                                                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 二、执行流程对比

### 原版执行流程

```
用户输入 "AI 发展历史"
  │
  ▼
DeepResearchAgent.research("AI 发展历史")
  │
  ├── yield "正在初始化..."
  │
  ├── state = SummaryState(research_topic="AI 发展历史")
  │
  ├── yield "正在规划..."
  │
  ├── todo_list = self.planner.plan_todo_list(state)
  │     │
  │     ├── ToolAwareSimpleAgent("TODO Planner").run(prompt)
  │     │     └── HelloAgentsLLM.invoke(messages)
  │     └── _extract_tasks(response) → [TodoItem, TodoItem, TodoItem]
  │
  ├── yield "已规划 3 个子任务"
  │
  ├── for idx, task in enumerate(todo_list):  ← 串行
  │     │
  │     ├── yield "正在研究任务 1/3：AI 的起源"
  │     ├── yield "正在搜索：AI history origins"
  │     │
  │     ├── search_results = self.search_service.search("AI history origins")
  │     │     └── TavilyClient.search("AI history origins")
  │     │
  │     ├── yield "正在总结搜索结果..."
  │     │
  │     ├── summary, urls = self.summarizer.summarize_task(task, search_results)
  │     │     │
  │     │     ├── ToolAwareSimpleAgent("Task Summarizer").run(prompt)
  │     │     │     └── HelloAgentsLLM.invoke(messages)
  │     │     └── return (summary, source_urls)
  │     │
  │     └── yield "任务 1 完成"
  │     │
  │     ├── yield "正在研究任务 2/3：AI 的发展"
  │     ├── ... (重复搜索+总结)
  │     │
  │     └── yield "任务 2 完成"
  │
  ├── yield "正在生成最终报告..."
  │
  ├── report = self.reporter.generate_report(topic, task_summaries)
  │     │
  │     ├── if total_tasks <= 2:
  │     │     └── ToolAwareSimpleAgent("Report Writer").run(prompt)
  │     │           └── HelloAgentsLLM.invoke(messages)
  │     │
  │     └── else:  ← 批处理
  │           ├── batches = split_into_batches(task_summaries)
  │           ├── for batch in batches:
  │           │     └── partial_report = _generate_partial_report(batch)
  │           └── final = _merge_partial_reports(partial_reports)
  │
  └── yield "研究完成" (report)
```

### LangGraph 版执行流程

```
用户输入 "AI 发展历史"
  │
  ▼
LangGraphAgent.research("AI 发展历史")
  │
  └── initial_state = {
        "query": "AI 发展历史",
        "sub_tasks": [],
        "current_task_index": 0,
        "draft_report": "", "critique": "", "final_report": "",
        "iterations": 0, "status": "starting", "error": None
      }
  │
  └── graph.astream_events(initial_state)
        │
        ├── [on_chain_start:decompose]
        │     └── yield "正在规划研究任务..."
        │
        ├── decompose_topic(state, llm)
        │     ├── prompt = todo_planner_instructions.format(...)
        │     ├── response = llm.invoke([SystemMessage, HumanMessage(prompt)]).content
        │     │     └── HelloAgentsChatModel._generate()
        │     │           └── MultiProviderLLM.invoke()
        │     └── return {"sub_tasks": [...], "current_task_index": 0}
        │
        ├── [on_chain_end:decompose]
        │     └── yield "已规划 3 个子任务"
        │
        ├── [on_chain_start:fan_out]
        │     └── yield "正在并行搜索..."
        │
        ├── _fan_out_router(state)
        │     └── return [
        │           Send("search_sub_task", {**state, "current_task_index": 0}),
        │           Send("search_sub_task", {**state, "current_task_index": 1}),
        │           Send("search_sub_task", {**state, "current_task_index": 2}),
        │         ]
        │
        ├── [并行执行]
        │     ├── search_sub_task(state_0)
        │     │     ├── results = SearchService.search("AI history origins")
        │     │     └── return {"sub_tasks": updated}
        │     │
        │     ├── search_sub_task(state_1)
        │     │     ├── results = SearchService.search("AI development timeline")
        │     │     └── return {"sub_tasks": updated}
        │     │
        │     └── search_sub_task(state_2)
        │           ├── results = SearchService.search("AI future trends")
        │           └── return {"sub_tasks": updated}
        │
        ├── [on_chain_end:search_sub_task] × 3
        │     └── yield "任务 N 搜索完成，找到 M 条结果"
        │
        ├── [on_chain_start:summarize]
        │     └── yield "正在总结搜索结果..."
        │
        ├── summarize_tasks(state, llm)
        │     ├── for task in sub_tasks:
        │     │     ├── prompt = task_summarizer_instructions.format(...)
        │     │     └── summary = llm.invoke([SystemMessage, HumanMessage(prompt)]).content
        │     └── return {"sub_tasks": updated}
        │
        ├── [on_chain_start:generate_report]
        │     └── yield "正在生成报告..."
        │
        ├── generate_report(state, llm)
        │     ├── prompt = report_writer_instructions.format(...)
        │     └── report = llm.invoke([SystemMessage, HumanMessage(prompt)]).content
        │     └── return {"draft_report": report}
        │
        ├── [on_chain_start:reflect]
        │     └── yield "正在审查报告质量..."
        │
        ├── reflect_report(state, llm)
        │     ├── prompt = critique_prompt.format(query, draft_report)
        │     └── critique = llm.invoke([SystemMessage, HumanMessage(prompt)]).content
        │     └── return {"critique": critique}
        │
        ├── should_continue(state)
        │     ├── if "APPROVED" in critique → "finalize"
        │     ├── if iterations >= 2 → "finalize"
        │     └── else → "revise"
        │
        ├── (如果需要修改)
        │     ├── [on_chain_start:revise]
        │     │     └── yield "正在修改报告..."
        │     │
        │     ├── revise_report(state, llm)
        │     │     ├── prompt = revise_prompt.format(query, draft, critique)
        │     │     └── revised = llm.invoke([SystemMessage, HumanMessage(prompt)]).content
        │     │     └── return {"draft_report": revised, "iterations": 1}
        │     │
        │     └── reflect_report(state, llm)  ← 循环
        │           └── ...
        │
        ├── [on_chain_start:finalize]
        │     └── yield "正在完成报告..."
        │
        ├── finalize_report(state)
        │     └── return {"final_report": state["draft_report"], "status": "completed"}
        │
        └── [on_chain_end:finalize]
              └── yield "研究完成" (final_report)
```

## 三、关键差异对比表

| 维度 | 原版 | LangGraph 版 |
|------|------|--------------|
| **状态管理** | `SummaryState` (Pydantic) 手动传递 | `ResearchState` (TypedDict) 自动合并 |
| **任务执行** | `for` 循环串行 | `Send API` 并行 |
| **LLM 调用** | `HelloAgentsLLM.invoke()` 直接调用 | `HelloAgentsChatModel` → `BaseChatModel` 包装 |
| **SSE 输出** | 手动 `_format_sse_event()` | `graph.astream_events()` 自动触发 |
| **质量审查** | 无 | `reflect` → `revise` → `reflect` 循环 |
| **批处理** | `ReportingService` 内部分批合并 | 不需要 (并行搜索后一次性生成) |
| **容错** | `RetryableLLM` 手动重试 | `recursion_limit` + 条件边 |
| **可扩展性** | 修改多处代码 | 添加节点即可 |
| **代码量** | ~236 行 (agent.py) + 多个服务文件 | ~180 行 (agent_langgraph.py) + 图模块 |

## 四、LLM 调用链路对比

### 原版 LLM 调用

```
PlanningService.plan_todo_list()
  └── ToolAwareSimpleAgent.run()
        └── RetryableLLM.invoke()
              └── HelloAgentsLLM.invoke()
                    └── openai.OpenAI().chat.completions.create()

SummarizationService.summarize_task()
  └── ToolAwareSimpleAgent.run()
        └── RetryableLLM.invoke()
              └── HelloAgentsLLM.invoke()
                    └── openai.OpenAI().chat.completions.create()

ReportingService.generate_report()
  └── ToolAwareSimpleAgent.run()
        └── RetryableLLM.invoke()
              └── HelloAgentsLLM.invoke()
                    └── openai.OpenAI().chat.completions.create()
```

### LangGraph 版 LLM 调用

```
decompose_topic(state, llm)
summarize_tasks(state, llm)
generate_report(state, llm)
reflect_report(state, llm)
revise_report(state, llm)
  └── llm.invoke(messages)
        └── HelloAgentsChatModel._generate()
              ├── _to_openai_messages(messages)
              └── self._llm.invoke(openai_msgs)
                    └── MultiProviderLLM.invoke()
                          └── HelloAgentsLLM.invoke()
                                └── openai.OpenAI().chat.completions.create()
```

## 五、状态更新对比

### 原版状态更新

```python
# 手动管理
state = SummaryState(research_topic=topic)
todo_list = self.planner.plan_todo_list(state)  # 返回新列表

for task in todo_list:
    search_results = self.search_service.search(task.query)
    summary, urls = self.summarizer.summarize_task(task, search_results)
    task.summary = summary        # 直接修改对象
    task.source_urls = urls
    task_summaries.append((task, summary, urls))  # 手动收集

report = self.reporter.generate_report(topic, task_summaries)
```

### LangGraph 版状态更新

```python
# 自动合并 (每个节点返回部分更新)
decompose_topic() → {"sub_tasks": [...], "current_task_index": 0}
search_sub_task() → {"sub_tasks": updated_sub_tasks}
summarize_tasks() → {"sub_tasks": updated_sub_tasks}
generate_report() → {"draft_report": "..."}
reflect_report()  → {"critique": "..."}
revise_report()   → {"draft_report": "...", "iterations": 1}
finalize_report() → {"final_report": "...", "status": "completed"}
```
