from pydantic import BaseModel
from typing import Optional, List, Any


class QueryRequest(BaseModel):
    sql: str
    limit: Optional[int] = 100
    format: str = "table"  # table, json, csv


class QueryResponse(BaseModel):
    success: bool
    data: Optional[List[Any]] = None
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    formatted: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    uptime_seconds: float
    connection_count: int
    active_queries: int
