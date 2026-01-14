from fastapi import FastAPI
from daemon.models import QueryRequest, QueryResponse, HealthResponse
from daemon.connection import SnowflakeConnection
from daemon.executor import QueryExecutor
from daemon.state import StateManager, SessionState
import time
import os
import signal

app = FastAPI(title="Snowflake Daemon")
start_time = time.time()

# Global connection, state manager, and executor (will improve in Phase 3 with connection pool)
state_manager = StateManager()
try:
    connection = SnowflakeConnection()
    executor = QueryExecutor(connection, state_manager)
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


@app.get("/state")
async def get_state() -> SessionState:
    """Get current session state (database, schema, warehouse, role)."""
    return state_manager.get_state()


@app.post("/shutdown")
async def shutdown():
    """Gracefully shutdown the daemon."""
    # Close Snowflake connection
    if connection_available and connection:
        connection.close()

    # Schedule shutdown signal (delayed to allow response to be sent)
    def trigger_shutdown():
        time.sleep(0.5)  # Give time for response to be sent
        os.kill(os.getpid(), signal.SIGTERM)

    import threading
    threading.Thread(target=trigger_shutdown, daemon=True).start()

    return {"status": "shutting down"}


# Entry point for manual testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
