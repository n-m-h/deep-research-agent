"""
数据模型
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TodoItem(BaseModel):
    id: int
    title: str
    intent: str
    query: str
    status: TaskStatus = TaskStatus.PENDING
    summary: Optional[str] = None
    source_urls: List[str] = []


class SummaryState(BaseModel):
    research_topic: str
    current_date: str = datetime.now().strftime("%Y年%m月%d日")
    todo_list: List[TodoItem] = []
    created_at: datetime = datetime.now()


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "unknown"


class ResearchEvent(BaseModel):
    type: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    task_id: Optional[int] = None
    percentage: Optional[float] = None
    stage: Optional[str] = None


class ResearchRequest(BaseModel):
    topic: str
    search_api: Optional[str] = "tavily"


class ResearchResponse(BaseModel):
    status: str
    message: str
    report: Optional[str] = None
    tasks: Optional[List[Dict[str, Any]]] = None
