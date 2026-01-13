from fastapi import FastAPI
from daemon.models import QueryRequest, QueryResponse, HealthResponse
import time

app = FastAPI(title="Snowflake Daemon")
start_time = time.time()


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        uptime_seconds=time.time() - start_time,
        connection_count=0,
        active_queries=0
    )


@app.post("/query")
async def execute_query(request: QueryRequest) -> QueryResponse:
    # TODO: Implement actual query execution
    return QueryResponse(
        success=False,
        error="Not implemented yet"
    )


# Entry point for manual testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
