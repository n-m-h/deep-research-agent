# LangGraph 版本架构详解

## 一、整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    用户请求 (topic)                                  │
└─────────────────────────────────┬───────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI (main.py)                                       │
│                                                                                      │
│  @app.post("/research/stream")  ──▶  async def research_stream()                    │
│  @app.post("/research")         ──▶  async def research()                            │
│                                                                                      │
│  USE_LANGGRAPH=true → LangGraphAgent                                                 │
│  USE_LANGGRAPH=false → DeepResearchAgent (原版)                                      │
└─────────────────────────────────┬───────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            LangGraphAgent (agent_langgraph.py)                       │
│                                                                                      │
│  __init__()                                                                          │
│    ├── create_chat_model(config) ──▶ HelloAgentsChatModel (包装 HelloAgentsLLM)      │
│    └── build_research_graph(llm) ──▶ StateGraph (编译后的图)                         │
│                                                                                      │
│  research(topic) ──▶ graph.astream_events(initial_state) ──▶ AsyncGenerator[SSE]     │
│  run(topic)      ──▶ graph.invoke(initial_state)           ──▶ str (完整报告)        │
└─────────────────────────────────┬───────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           StateGraph 工作流 (graph/)                                 │
│                                                                                      │
│  ┌───────────┐     ┌──────────┐     ┌─────────────────────────────┐                │
│  │ decompose │ ──▶ │ fan_out  │ ──▶ │   Send API 并行分发          │                │
│  │ (LLM)     │     │ (router) │     │                             │                │
│  └───────────┘     └──────────┘     │  ┌──────────┐  ┌──────────┐ │                │
│                                      │  │search_0  │  │search_1  │ │                │
│                                      │  │search_2  │  │...       │ │                │
│                                      │  └────┬─────┘  └────┬─────┘ │                │
│                                      └───────┼──────────────┼───────┘                │
│                                              │              │                         │
│                                              ▼              ▼                         │
│                                      ┌─────────────────────────────┐                │
│                                      │        summarize            │                │
│                                      │          (LLM)              │                │
│                                      └──────────────┬──────────────┘                │
│                                                     │                                │
│                                                     ▼                                │
│                                      ┌─────────────────────────────┐                │
│                                      │      generate_report        │                │
│                                      │          (LLM)              │                │
│                                      └──────────────┬──────────────┘                │
│                                                     │                                │
│                                                     ▼                                │
│                                      ┌─────────────────────────────┐                │
│                                      │         reflect             │                │
│                                      │          (LLM)              │                │
│                                      └──────────────┬──────────────┘                │
│                                                     │                                │
│                                        ┌────────────┴────────────┐                  │
│                                        │    should_continue()    │                  │
│                                        │    (条件路由路由器)       │                  │
│                                        └────────────┬────────────┘                  │
│                                                     │                                │
│                              ┌──────────────────────┼──────────────────────┐        │
│                              │ APPROVED / 达到上限   │  NEEDS_REVISION       │        │
│                              ▼                      ▼                       │        │
│                      ┌──────────────┐        ┌──────────────┐               │        │
│                      │  finalize    │        │    revise     │               │        │
│                      │              │        │     (LLM)     │               │        │
│                      └──────┬───────┘        └──────┬───────┘               │        │
│                             │                       │                        │        │
│                             ▼                       └────────────────────────┘        │
│                          END                                                          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 二、方法调用链

### 2.1 初始化阶段

```
main.py
  │
  ├── import: USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false")
  │   └── if USE_LANGGRAPH: from agent_langgraph import LangGraphAgent
  │
  └── @app.post("/research/stream")
        │
        └── agent = LangGraphAgent()
              │
              ├── self.chat_model = create_chat_model(config)
              │     │
              │     ├── primary_llm = HelloAgentsLLM(...)
              │     │     └── 包装 OpenAI SDK
              │     │
              │     ├── backup_llms = [HelloAgentsLLM(...), ...]
              │     │     └── 从 config.llm_providers 加载
              │     │
              │     ├── llm = MultiProviderLLM(primary_llm, backup_llms)
              │     │     └── 自动故障切换
              │     │
              │     └── return HelloAgentsChatModel(llm=llm)
              │           └── 继承 BaseChatModel
              │               ├── _generate() ──▶ llm.invoke(messages)
              │               └── _stream()   ──▶ llm.think(messages)
              │
              └── self.graph = build_research_graph(self.chat_model)
                    │
                    ├── builder = StateGraph(ResearchState)
                    │
                    ├── decompose_node = partial(decompose_topic, llm=llm)
                    ├── summarize_node = partial(summarize_tasks, llm=llm)
                    ├── report_node  = partial(generate_report, llm=llm)
                    ├── reflect_node = partial(reflect_report, llm=llm)
                    ├── revise_node  = partial(revise_report, llm=llm)
                    │
                    ├── builder.add_node("decompose", decompose_node)
                    ├── builder.add_node("search_sub_task", search_sub_task)
                    ├── builder.add_node("summarize", summarize_node)
                    ├── builder.add_node("generate_report", report_node)
                    ├── builder.add_node("reflect", reflect_node)
                    ├── builder.add_node("revise", revise_node)
                    ├── builder.add_node("finalize", finalize_report)
                    │
                    ├── builder.set_entry_point("decompose")
                    ├── builder.add_edge("decompose", "fan_out")
                    ├── builder.add_conditional_edges("fan_out", _fan_out_router, ["search_sub_task"])
                    ├── builder.add_edge("search_sub_task", "summarize")
                    ├── builder.add_edge("summarize", "generate_report")
                    ├── builder.add_edge("generate_report", "reflect")
                    ├── builder.add_conditional_edges("reflect", should_continue, {...})
                    ├── builder.add_edge("revise", "reflect")
                    ├── builder.add_edge("finalize", END)
                    │
                    └── return builder.compile()
```

### 2.2 流式研究 (research)

```
LangGraphAgent.research(topic)
  │
  ├── initial_state = {
  │     "query": topic,
  │     "sub_tasks": [],
  │     "current_task_index": 0,
  │     "draft_report": "",
  │     "critique": "",
  │     "final_report": "",
  │     "iterations": 0,
  │     "status": "starting",
  │     "error": None,
  │   }
  │
  └── async for event in self.graph.astream_events(initial_state, version="v2"):
        │
        ├── kind = event["event"]          # "on_chain_start" / "on_chain_end"
        ├── name = event["name"]           # 节点名称 ("decompose", "search_sub_task", ...)
        ├── data = event["data"]           # {"input": ..., "output": ...}
        │
        └── if kind == "on_chain_start":
              │
              ├── name == "decompose"     ──▶ yield "正在规划研究任务..."
              ├── name == "fan_out"       ──▶ yield "正在并行搜索..."
              ├── name == "search_sub_task" ──▶ yield "正在搜索：{task_title}"
              ├── name == "summarize"     ──▶ yield "正在总结搜索结果..."
              ├── name == "generate_report" ──▶ yield "正在生成报告..."
              ├── name == "reflect"       ──▶ yield "正在审查报告质量..."
              ├── name == "revise"        ──▶ yield "正在修改报告..."
              └── name == "finalize"      ──▶ yield "正在完成报告..."
            │
            └── elif kind == "on_chain_end":
                  │
                  ├── name == "decompose" ──▶ yield tasks 列表 (percentage=15)
                  ├── name == "search_sub_task" ──▶ yield 搜索完成 (result_count)
                  └── name == "finalize"  ──▶ yield 最终报告 (percentage=100, stage="completed")
```

### 2.3 图节点执行详解

#### Node 1: decompose_topic

```
decompose_topic(state, llm)
  │
  ├── prompt = todo_planner_instructions.format(
  │     current_date=datetime.now(),
  │     research_topic=state["query"]
  │   )
  │
  ├── messages = [
  │     SystemMessage("研究规划专家..."),
  │     HumanMessage(prompt)
  │   ]
  │
  ├── response = llm.invoke(messages).content
  │     │
  │     └── HelloAgentsChatModel._generate()
  │           │
  │           ├── _to_openai_messages(messages)
  │           │   └── [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
  │           │
  │           └── self._llm.invoke(openai_msgs)
  │                 │
  │                 └── MultiProviderLLM.invoke()
  │                       │
  │                       └── HelloAgentsLLM.invoke()
  │                             │
  │                             └── openai.OpenAI().chat.completions.create()
  │
  ├── tasks = _extract_tasks(response)
  │     │
  │     ├── 清理 markdown 代码块标记
  │     ├── 修复 Unicode 引号
  │     └── json.loads(response)
  │
  └── return {
        "sub_tasks": [
          {"id": 1, "title": "...", "intent": "...", "query": "...",
           "search_results": [], "summary": "", "source_urls": []},
          ...
        ],
        "current_task_index": 0
      }
```

#### Node 2: search_sub_task (并行)

```
search_sub_task(state)  ← 被 Send API 调用 N 次 (每个子任务一次)
  │
  ├── idx = state["current_task_index"]
  ├── task = state["sub_tasks"][idx]
  │
  ├── results = search_service.search(task["query"])
  │     │
  │     └── SearchService.search(query)
  │           │
  │           └── _search_with_tavily(query, max_results)
  │                 │
  │                 ├── signal.alarm(8)  ← 超时保护
  │                 ├── tavily_client.search(query, ...)
  │                 └── signal.alarm(0)
  │                 │
  │                 └── return [
  │                       {"title": "...", "url": "...", "snippet": "...", "source": "tavily"},
  │                       ...
  │                     ]
  │
  ├── updated_task = {**task}
  │   updated_task["search_results"] = results
  │   updated_task["source_urls"] = [r["url"] for r in results]
  │
  └── return {"sub_tasks": updated_sub_tasks}
```

#### Node 3: summarize_tasks

```
summarize_tasks(state, llm)
  │
  └── for idx, task in enumerate(sub_tasks):
        │
        ├── formatted_sources = _format_sources(task["search_results"])
        │
        ├── prompt = task_summarizer_instructions.format(
        │     task_title=task["title"],
        │     task_intent=task["intent"],
        │     task_query=task["query"],
        │     search_results=formatted_sources
        │   )
        │
        ├── messages = [
        │     SystemMessage("任务总结专家..."),
        │     HumanMessage(prompt)
        │   ]
        │
        ├── summary = llm.invoke(messages).content
        │
        └── sub_tasks[idx]["summary"] = summary
        │
  └── return {"sub_tasks": sub_tasks}
```

#### Node 4: generate_report

```
generate_report(state, llm)
  │
  ├── formatted_summaries = _format_summaries(sub_tasks)
  │     │
  │     └── "## 任务1：标题\n\n**意图**：...\n\n总结内容\n\n**来源**：\n- url1\n- url2\n"
  │
  ├── prompt = report_writer_instructions.format(
  │     research_topic=state["query"],
  │     task_summaries=formatted_summaries
  │   )
  │
  ├── messages = [
  │     SystemMessage("报告撰写专家..."),
  │     HumanMessage(prompt)
  │   ]
  │
  └── report = llm.invoke(messages).content
  │
  └── return {"draft_report": report}
```

#### Node 5: reflect_report

```
reflect_report(state, llm)
  │
  ├── critique_prompt = f"""
  │   研究主题：{state["query"]}
  │   报告内容：{state["draft_report"]}
  │   
  │   请从以下方面评估：
  │   1. 覆盖度  2. 准确性  3. 结构  4. 引用  5. 改进建议
  │   
  │   格式：VERDICT: APPROVED/NEEDS_REVISION
  │         ISSUES: [...]
  │         SUGGESTIONS: [...]
  │   """
  │
  ├── messages = [
  │     SystemMessage("报告审查专家..."),
  │     HumanMessage(critique_prompt)
  │   ]
  │
  └── critique = llm.invoke(messages).content
  │
  └── return {"critique": critique}
```

#### Node 6: revise_report

```
revise_report(state, llm)
  │
  ├── revise_prompt = f"""
  │   研究主题：{state["query"]}
  │   原报告：{state["draft_report"]}
  │   审查意见：{state["critique"]}
  │   
  │   请修改报告，解决所有指出的问题。
  │   """
  │
  ├── messages = [
  │     SystemMessage("报告修改专家..."),
  │     HumanMessage(revise_prompt)
  │   ]
  │
  └── revised = llm.invoke(messages).content
  │
  └── return {"draft_report": revised, "iterations": iterations + 1}
```

#### Node 7: finalize_report

```
finalize_report(state)
  │
  └── return {"final_report": state["draft_report"], "status": "completed"}
```

### 三、State 流转详解

```
ResearchState (TypedDict)
  │
  ├── query: str                    # 研究主题 (输入，不变)
  ├── sub_tasks: List[SubTask]     # 子任务列表 (decompose 创建，search/summarize 更新)
  │   └── SubTask:
  │       ├── id: int
  │       ├── title: str
  │       ├── intent: str
  │       ├── query: str
  │       ├── search_results: List[dict]   # search_sub_task 填充
  │       ├── summary: str                 # summarize_tasks 填充
  │       └── source_urls: List[str]       # search_sub_task 填充
  │
  ├── current_task_index: int      # 当前搜索任务索引 (Send API 使用)
  ├── draft_report: str            # 草稿报告 (generate_report 创建，revise 更新)
  ├── critique: str                # 审查意见 (reflect_report 创建)
  ├── final_report: str            # 最终报告 (finalize_report 创建)
  ├── iterations: int              # 修改迭代次数 (revise_report 递增)
  ├── status: str                  # 状态标识
  └── error: Optional[str]         # 错误信息
```

### 四、Send API 并行机制

```
fan_out 节点触发 _fan_out_router(state):
  │
  └── return [
        Send("search_sub_task", {**state, "current_task_index": 0}),
        Send("search_sub_task", {**state, "current_task_index": 1}),
        Send("search_sub_task", {**state, "current_task_index": 2}),
        ...
      ]
         │
         ├── search_sub_task(state_0) ──▶ 搜索任务 0 ──▶ 更新 sub_tasks[0]
         ├── search_sub_task(state_1) ──▶ 搜索任务 1 ──▶ 更新 sub_tasks[1]
         ├── search_sub_task(state_2) ──▶ 搜索任务 2 ──▶ 更新 sub_tasks[2]
         │
         └── 所有并行任务完成后，状态合并 ──▶ 进入 summarize 节点
```

### 五、质量审查循环

```
reflect ──▶ should_continue(state)
              │
              ├── "APPROVED" in critique.upper()
              │   └── return "finalize" ──▶ finalize ──▶ END
              │
              ├── iterations >= 2
              │   └── return "finalize" ──▶ finalize ──▶ END
              │
              └── else
                  └── return "revise" ──▶ revise ──▶ reflect (循环)
```

### 六、LLM 调用链路

```
节点调用 llm.invoke(messages)
  │
  └── HelloAgentsChatModel._generate(messages)
        │
        ├── _to_openai_messages(messages)
        │   └── LangChain Message → OpenAI format dict
        │
        └── self._llm.invoke(openai_msgs)
              │
              └── MultiProviderLLM.invoke()
                    │
                    ├── _try_current_llm(primary_llm.invoke, ...)
                    │   │
                    │   └── HelloAgentsLLM.invoke()
                    │         │
                    │         └── openai.OpenAI().chat.completions.create(
                    │               model=config.llm_model_id,
                    │               messages=openai_msgs,
                    │               temperature=config.llm_temperature,
                    │               ...
                    │             )
                    │
                    └── (失败时) _retry_with_fallback()
                          │
                          └── 遍历 backup_llms，直到成功或全部失败
```

### 七、SSE 事件流

```
graph.astream_events() 输出事件 ──▶ LangGraphAgent.research() 转换 ──▶ FastAPI StreamingResponse

LangGraph 事件                        SSE 输出
─────────────────────────────────────────────────────────────────────
on_chain_start:decompose         ──▶ data: {"type":"status","message":"正在规划研究任务...","percentage":10}
on_chain_end:decompose           ──▶ data: {"type":"tasks","message":"已规划 N 个子任务","data":{"tasks":[...]},...}
on_chain_start:fan_out           ──▶ data: {"type":"status","message":"正在并行搜索...","percentage":20}
on_chain_start:search_sub_task   ──▶ data: {"type":"task_progress","message":"正在搜索：{title}","task_id":N}
on_chain_end:search_sub_task     ──▶ data: {"type":"status","message":"任务 N 搜索完成，找到 M 条结果",...}
on_chain_start:summarize         ──▶ data: {"type":"status","message":"正在总结搜索结果...","percentage":50}
on_chain_start:generate_report   ──▶ data: {"type":"status","message":"正在生成报告...","percentage":75}
on_chain_start:reflect           ──▶ data: {"type":"status","message":"正在审查报告质量...","percentage":85}
on_chain_start:revise            ──▶ data: {"type":"status","message":"正在修改报告...","percentage":88}
on_chain_start:finalize          ──▶ data: {"type":"status","message":"正在完成报告...","percentage":95}
on_chain_end:finalize            ──▶ data: {"type":"report","message":"研究完成","data":{"report":"..."},"percentage":100,"stage":"completed"}
```
