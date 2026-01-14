from fastapi import FastAPI
from daemon.models import QueryRequest, QueryResponse, HealthResponse
from daemon.connection import SnowflakeConnection
from daemon.executor import QueryExecutor
import time

app = FastAPI(title="Snowflake Daemon")
start_time = time.time()

# Global connection and executor (will improve in Phase 2 with connection pool)
try:
    connection = SnowflakeConnection()
    executor = QueryExecutor(connection)
    connection_available = True
except ValueError as e:
    # Missing credentials - daemon will start but queries will fail with helpful error
    connection = None
    executor = None
    connection_available = False
    connection_error = str(e)


@app.get("/health")
async def health() -> HealthResponse:
    conn_count = 1 if connection_available and connection and connection.is_healthy() else 0
    status = "healthy" if connection_available else "degraded"

    return HealthResponse(
        status=status,
        uptime_seconds=time.time() - start_time,
        connection_count=conn_count,
        active_queries=0
    )


@app.post("/query")
async def execute_query(request: QueryRequest) -> QueryResponse:
    if not connection_available:
        return QueryResponse(
            success=False,
            error=f"Snowflake connection not configured: {connection_error}"
        )

    response = await executor.execute(request.sql, request.limit)
    return response


# Entry point for manual testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
