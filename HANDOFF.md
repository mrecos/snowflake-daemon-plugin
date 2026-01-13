# Snowflake Daemon Plugin - Stateful Connection Architecture

## Executive Summary

Build a **session-persistent Snowflake plugin** using a lightweight Python daemon that maintains persistent database connections. This solves the critical limitation of the original plugin where each command created a new connection, preventing context (database/schema/warehouse) from persisting.

**Key Innovation:** Background daemon maintains a persistent Snowflake connection pool, enabling true session management while preserving the simple "open Claude Code and just use it" workflow.

**Architecture:**
```
Claude Code Plugin (commands/skills)
        ↓ (HTTP/Socket)
Lightweight Python Daemon (FastAPI)
        ↓ (persistent connection)
    Snowflake Database
```

---

## Architecture Overview

### Core Components

1. **Daemon Server** (`daemon/server.py`)
   - FastAPI HTTP server on localhost:8765
   - Manages persistent Snowflake connections
   - Maintains session state (database, schema, warehouse, role)
   - Auto-starts on first plugin command
   - Auto-stops after idle timeout (configurable, default 30 minutes)

2. **Connection Pool** (`daemon/connection_pool.py`)
   - Maintains 1-5 persistent Snowflake connections
   - Connection health monitoring with auto-reconnect
   - Session state tracking per connection
   - Connection reuse strategy

3. **Query Executor** (`daemon/executor.py`)
   - Executes queries on pooled connections
   - Preserves session context across queries
   - Transaction management
   - Result streaming for large datasets

4. **Plugin Commands** (`commands/`)
   - Lightweight HTTP client wrappers
   - Communicate with daemon via REST API
   - Start daemon if not running
   - Same user experience as original plugin

5. **State Manager** (`daemon/state.py`)
   - Tracks current database, schema, warehouse, role
   - Persists state across daemon restarts (optional)
   - Configuration management

### Technology Stack

**Core:**
- Python 3.10+
- FastAPI (async HTTP server)
- uvicorn (ASGI server)
- snowflake-connector-python (Snowflake connectivity)
- httpx (async HTTP client for commands)

**Additional:**
- pydantic (request/response models)
- python-dotenv (environment config)
- structlog (structured logging)

**Testing:**
- pytest (test framework)
- pytest-asyncio (async test support)
- pytest-mock (mocking)
- httpx (test client)

---

## Phased Implementation Plan

### Phase 1: Foundation - Basic Daemon (Week 1)

**Goal:** Get a minimal daemon running that can accept and execute queries

#### Milestone 1.1: Project Setup (Day 1)
```
snowflake-daemon-plugin/
├── .claude-plugin/
│   └── plugin.json
├── daemon/
│   ├── __init__.py
│   ├── server.py          # FastAPI server
│   └── models.py          # Pydantic models
├── tests/
│   ├── __init__.py
│   └── test_daemon.py
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

**Files to create:**

1. **`requirements.txt`**
```
fastapi>=0.104.0
uvicorn>=0.24.0
snowflake-connector-python>=3.12.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.25.0
structlog>=23.0.0
```

2. **`requirements-dev.txt`**
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
pytest-cov>=4.1.0
black>=23.0.0
ruff>=0.1.0
```

3. **`daemon/models.py`** - Pydantic request/response models
```python
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
```

4. **`daemon/server.py`** - Minimal FastAPI server
```python
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
```

**Unit Tests:**

5. **`tests/test_daemon.py`**
```python
import pytest
from fastapi.testclient import TestClient
from daemon.server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data

def test_query_endpoint_exists(client):
    response = client.post("/query", json={"sql": "SELECT 1"})
    assert response.status_code == 200
    # Will fail with "Not implemented yet" - that's expected
```

**Success Criteria:**
- [ ] FastAPI server starts on localhost:8765
- [ ] `/health` endpoint returns 200
- [ ] `/query` endpoint accepts requests
- [ ] Unit tests pass

---

#### Milestone 1.2: Connection Manager (Day 2-3)

**Goal:** Implement basic connection to Snowflake with PAT authentication

**Files to create:**

6. **`daemon/connection.py`** - Connection manager (reuse from existing codebase)
```python
import os
from typing import Optional
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

class SnowflakeConnection:
    """Manages a single Snowflake connection with session state."""

    def __init__(self):
        self.account = os.getenv('SNOWFLAKE_ACCOUNT')
        self.user = os.getenv('SNOWFLAKE_USER')
        self.password = os.getenv('SNOWFLAKE_PAT')
        self.warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        self.database = os.getenv('SNOWFLAKE_DATABASE')
        self.schema = os.getenv('SNOWFLAKE_SCHEMA')
        self.role = os.getenv('SNOWFLAKE_ROLE')

        self._connection: Optional[snowflake.connector.SnowflakeConnection] = None
        self._validate_config()

    def _validate_config(self):
        """Validate required configuration."""
        required = ['SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_PAT']
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    def connect(self) -> snowflake.connector.SnowflakeConnection:
        """Establish connection to Snowflake."""
        if self._connection is None or self._connection.is_closed():
            self._connection = snowflake.connector.connect(
                account=self.account,
                user=self.user,
                password=self.password,
                warehouse=self.warehouse,
                database=self.database,
                schema=self.schema,
                role=self.role
            )
        return self._connection

    def close(self):
        """Close the connection."""
        if self._connection and not self._connection.is_closed():
            self._connection.close()
            self._connection = None

    def is_healthy(self) -> bool:
        """Check if connection is active and healthy."""
        try:
            if self._connection is None or self._connection.is_closed():
                return False
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
```

**Unit Tests:**

7. **`tests/test_connection.py`**
```python
import pytest
from unittest.mock import Mock, patch
from daemon.connection import SnowflakeConnection

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('SNOWFLAKE_ACCOUNT', 'test_account')
    monkeypatch.setenv('SNOWFLAKE_USER', 'test_user')
    monkeypatch.setenv('SNOWFLAKE_PAT', 'test_token')

def test_connection_validation_fails_without_credentials():
    with pytest.raises(ValueError, match="Missing required env vars"):
        SnowflakeConnection()

def test_connection_validation_succeeds(mock_env):
    conn = SnowflakeConnection()
    assert conn.account == 'test_account'
    assert conn.user == 'test_user'

@patch('snowflake.connector.connect')
def test_connect_creates_connection(mock_connect, mock_env):
    mock_connect.return_value = Mock()
    conn = SnowflakeConnection()
    result = conn.connect()
    assert result is not None
    mock_connect.assert_called_once()

@patch('snowflake.connector.connect')
def test_is_healthy_returns_true_for_active_connection(mock_connect, mock_env):
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.is_closed.return_value = False
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    conn = SnowflakeConnection()
    conn.connect()
    assert conn.is_healthy() is True
```

**Success Criteria:**
- [ ] Connection manager validates credentials
- [ ] Successfully connects to Snowflake
- [ ] Health check works
- [ ] Unit tests pass (mocked)
- [ ] Integration test with real Snowflake passes

---

#### Milestone 1.3: Basic Query Execution (Day 4-5)

**Goal:** Execute SELECT queries and return results

**Files to update:**

8. **`daemon/executor.py`** - Query executor
```python
from typing import Optional, Tuple
from daemon.connection import SnowflakeConnection
from daemon.models import QueryResponse
import time

class QueryExecutor:
    """Executes queries against Snowflake connection."""

    def __init__(self, connection: SnowflakeConnection):
        self.connection = connection

    def _validate_query(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate query (start with read-only)."""
        sql_upper = sql.strip().upper()

        # Allow SELECT and SHOW
        allowed_starts = ['SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'DESC']
        if not any(sql_upper.startswith(cmd) for cmd in allowed_starts):
            return False, f"Only read-only queries allowed: {sql_upper.split()[0]}"

        return True, None

    async def execute(self, sql: str, limit: Optional[int] = 100) -> QueryResponse:
        """Execute query and return results."""
        start_time = time.time()

        # Validate
        is_valid, error = self._validate_query(sql)
        if not is_valid:
            return QueryResponse(success=False, error=error)

        # Add LIMIT for SELECT queries
        sql_upper = sql.strip().upper()
        if limit and 'LIMIT' not in sql_upper and sql_upper.startswith('SELECT'):
            sql = f"{sql.rstrip(';')} LIMIT {limit}"

        try:
            conn = self.connection.connect()
            cursor = conn.cursor()
            cursor.execute(sql)

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            cursor.close()

            execution_time = time.time() - start_time

            return QueryResponse(
                success=True,
                data=rows,
                columns=columns,
                row_count=len(rows),
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return QueryResponse(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
```

9. **Update `daemon/server.py`** - Wire executor to endpoint
```python
from daemon.connection import SnowflakeConnection
from daemon.executor import QueryExecutor

# Global connection and executor (will improve in Phase 2)
connection = SnowflakeConnection()
executor = QueryExecutor(connection)

@app.post("/query")
async def execute_query(request: QueryRequest) -> QueryResponse:
    response = await executor.execute(request.sql, request.limit)
    return response
```

**Unit Tests:**

10. **`tests/test_executor.py`**
```python
import pytest
from daemon.executor import QueryExecutor
from daemon.connection import SnowflakeConnection
from unittest.mock import Mock, patch

@pytest.fixture
def mock_connection():
    conn = Mock(spec=SnowflakeConnection)
    return conn

def test_validate_query_allows_select(mock_connection):
    executor = QueryExecutor(mock_connection)
    is_valid, error = executor._validate_query("SELECT * FROM table")
    assert is_valid is True
    assert error is None

def test_validate_query_blocks_insert(mock_connection):
    executor = QueryExecutor(mock_connection)
    is_valid, error = executor._validate_query("INSERT INTO table VALUES (1)")
    assert is_valid is False
    assert "read-only" in error

@pytest.mark.asyncio
async def test_execute_adds_limit_to_select(mock_connection):
    mock_cursor = Mock()
    mock_cursor.description = [('col1',)]
    mock_cursor.fetchall.return_value = [(1,), (2,)]

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connection.connect.return_value = mock_conn

    executor = QueryExecutor(mock_connection)
    response = await executor.execute("SELECT * FROM table", limit=10)

    # Verify LIMIT was added
    call_args = mock_cursor.execute.call_args[0][0]
    assert "LIMIT 10" in call_args
```

**Success Criteria:**
- [ ] Executor validates queries
- [ ] Executes SELECT queries successfully
- [ ] Returns structured results
- [ ] Unit tests pass
- [ ] Integration test with real Snowflake passes

---

#### Milestone 1.4: Plugin Commands (Day 6-7)

**Goal:** Create Claude Code plugin commands that communicate with daemon

**Files to create:**

11. **`daemon/client.py`** - HTTP client for commands
```python
import httpx
import subprocess
import time
from typing import Optional

DAEMON_URL = "http://127.0.0.1:8765"
DAEMON_SCRIPT = "daemon/server.py"

class DaemonClient:
    """Client for communicating with the daemon."""

    def __init__(self, base_url: str = DAEMON_URL):
        self.base_url = base_url

    def is_running(self) -> bool:
        """Check if daemon is running."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=1.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def start_daemon(self) -> bool:
        """Start the daemon if not running."""
        if self.is_running():
            return True

        # Start daemon in background
        subprocess.Popen(
            ["python", "-m", "uvicorn", "daemon.server:app",
             "--host", "127.0.0.1", "--port", "8765"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for startup (max 5 seconds)
        for _ in range(50):
            time.sleep(0.1)
            if self.is_running():
                return True

        return False

    def query(self, sql: str, limit: int = 100, format: str = "table") -> dict:
        """Execute query via daemon."""
        if not self.start_daemon():
            return {"success": False, "error": "Failed to start daemon"}

        try:
            response = httpx.post(
                f"{self.base_url}/query",
                json={"sql": sql, "limit": limit, "format": format},
                timeout=300.0  # 5 minutes for long queries
            )
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
```

12. **`commands/sf-query.md`** - Query command
```markdown
---
description: Execute SQL query via persistent Snowflake connection
---

# Snowflake Query (Daemon)

Execute SELECT queries against Snowflake using persistent daemon connection.

## Usage

```bash
/snowflake-daemon:sf-query <sql>
/snowflake-daemon:sf-query <sql> [limit]
```

## Examples

```bash
# Basic query
/snowflake-daemon:sf-query SELECT * FROM customers

# With custom limit
/snowflake-daemon:sf-query SELECT * FROM orders 50
```

## Implementation

```bash
#!/bin/bash
python -c "
from daemon.client import DaemonClient
import sys

client = DaemonClient()
sql = '''$1'''
limit = int('$2') if len(sys.argv) > 2 else 100

result = client.query(sql, limit)

if result['success']:
    print(result.get('formatted', str(result['data'])))
    print(f\"\\nRows: {result['row_count']}\")
else:
    print(f\"Error: {result['error']}\", file=sys.stderr)
    sys.exit(1)
" "$@"
```
```

13. **`commands/sf-connect.md`** - Connection test
```markdown
---
description: Test connection to Snowflake daemon
---

# Test Snowflake Daemon Connection

Check if daemon is running and can connect to Snowflake.

## Usage

```bash
/snowflake-daemon:sf-connect
```

## Implementation

```bash
#!/bin/bash
python -c "
from daemon.client import DaemonClient

client = DaemonClient()

if not client.is_running():
    print('Starting daemon...')
    if not client.start_daemon():
        print('Failed to start daemon', file=sys.stderr)
        exit(1)
    print('Daemon started')

result = client.query('SELECT CURRENT_VERSION() as version, CURRENT_USER() as user')

if result['success']:
    print('✓ Connected to Snowflake')
    for row in result['data']:
        print(f'  Version: {row[0]}')
        print(f'  User: {row[1]}')
else:
    print(f'Connection failed: {result[\"error\"]}', file=sys.stderr)
    exit(1)
"
```
```

14. **`.claude-plugin/plugin.json`**
```json
{
  "name": "snowflake-daemon",
  "version": "1.0.0",
  "description": "Snowflake plugin with persistent daemon connection for session management",
  "author": {
    "name": "Matt Harris"
  },
  "keywords": [
    "snowflake",
    "sql",
    "database",
    "daemon",
    "persistent-connection"
  ],
  "homepage": "https://github.com/mattharris/snowflake-daemon-plugin",
  "license": "MIT"
}
```

**Success Criteria:**
- [ ] Commands can start daemon automatically
- [ ] Commands communicate with daemon
- [ ] `/sf-query` executes queries
- [ ] `/sf-connect` tests connection
- [ ] Daemon auto-starts on first command

---

### Phase 2: Session Management (Week 2)

**Goal:** Maintain session state (database, schema, warehouse, role) across queries

#### Milestone 2.1: State Tracking (Day 8-9)

**Files to create:**

15. **`daemon/state.py`** - Session state manager
```python
from typing import Optional
from pydantic import BaseModel

class SessionState(BaseModel):
    database: Optional[str] = None
    schema: Optional[str] = None
    warehouse: Optional[str] = None
    role: Optional[str] = None

class StateManager:
    """Manages session state for Snowflake connection."""

    def __init__(self):
        self.state = SessionState()

    def get_state(self) -> SessionState:
        """Get current session state."""
        return self.state

    def set_database(self, database: str):
        """Set current database."""
        self.state.database = database

    def set_schema(self, schema: str):
        """Set current schema."""
        self.state.schema = schema

    def set_warehouse(self, warehouse: str):
        """Set current warehouse."""
        self.state.warehouse = warehouse

    def set_role(self, role: str):
        """Set current role."""
        self.state.role = role
```

16. **Update `daemon/executor.py`** - Track USE commands
```python
class QueryExecutor:
    def __init__(self, connection: SnowflakeConnection, state_manager: StateManager):
        self.connection = connection
        self.state_manager = state_manager

    def _update_state_from_use_command(self, sql: str):
        """Update state when USE command is executed."""
        sql_upper = sql.strip().upper()

        if sql_upper.startswith('USE DATABASE'):
            db_name = sql_upper.replace('USE DATABASE', '').strip().strip(';')
            self.state_manager.set_database(db_name)
        elif sql_upper.startswith('USE SCHEMA'):
            schema_name = sql_upper.replace('USE SCHEMA', '').strip().strip(';')
            self.state_manager.set_schema(schema_name)
        elif sql_upper.startswith('USE WAREHOUSE'):
            wh_name = sql_upper.replace('USE WAREHOUSE', '').strip().strip(';')
            self.state_manager.set_warehouse(wh_name)
        elif sql_upper.startswith('USE ROLE'):
            role_name = sql_upper.replace('USE ROLE', '').strip().strip(';')
            self.state_manager.set_role(role_name)

    async def execute(self, sql: str, limit: Optional[int] = 100) -> QueryResponse:
        # ... existing validation ...

        # Track USE commands
        if sql_upper.startswith('USE'):
            self._update_state_from_use_command(sql)

        # ... execute query ...
```

17. **Add `/state` endpoint to `daemon/server.py`**
```python
@app.get("/state")
async def get_state():
    """Get current session state."""
    return state_manager.get_state()
```

18. **`commands/sf-context.md`** - Show current context
```markdown
---
description: Show current Snowflake session context
---

# Show Snowflake Context

Display current database, schema, warehouse, and role.

## Usage

```bash
/snowflake-daemon:sf-context
```

## Implementation

```bash
#!/bin/bash
python -c "
from daemon.client import DaemonClient

client = DaemonClient()
result = client.query('SELECT CURRENT_DATABASE() as db, CURRENT_SCHEMA() as schema, CURRENT_WAREHOUSE() as wh, CURRENT_ROLE() as role')

if result['success']:
    row = result['data'][0]
    print(f'Database: {row[0]}')
    print(f'Schema: {row[1]}')
    print(f'Warehouse: {row[2]}')
    print(f'Role: {row[3]}')
"
```
```

**Unit Tests:**

19. **`tests/test_state.py`**
```python
from daemon.state import StateManager, SessionState

def test_initial_state_is_empty():
    manager = StateManager()
    state = manager.get_state()
    assert state.database is None
    assert state.schema is None

def test_set_database_updates_state():
    manager = StateManager()
    manager.set_database("MY_DB")
    assert manager.get_state().database == "MY_DB"

def test_executor_tracks_use_database():
    # Mock connection and state manager
    # Execute "USE DATABASE MY_DB"
    # Assert state_manager.get_state().database == "MY_DB"
    pass
```

**Success Criteria:**
- [ ] State manager tracks session context
- [ ] USE commands update state
- [ ] `/sf-context` shows current state
- [ ] State persists across queries
- [ ] Unit tests pass

---

#### Milestone 2.2: USE Command Support (Day 10-11)

**Files to create:**

20. **`commands/sf-use.md`** - Switch context
```markdown
---
description: Switch database, schema, warehouse, or role
---

# Switch Snowflake Context

Change the active database, schema, warehouse, or role.

## Usage

```bash
/snowflake-daemon:sf-use database <name>
/snowflake-daemon:sf-use schema <name>
/snowflake-daemon:sf-use warehouse <name>
/snowflake-daemon:sf-use role <name>
```

## Examples

```bash
/snowflake-daemon:sf-use database ANALYTICS_DB
/snowflake-daemon:sf-use schema GOLD
/snowflake-daemon:sf-use warehouse COMPUTE_XL
```

## Implementation

```bash
#!/bin/bash
CONTEXT_TYPE=$(echo "$1" | tr '[:lower:]' '[:upper:]')
CONTEXT_NAME="$2"

python -c "
from daemon.client import DaemonClient

client = DaemonClient()
sql = 'USE $CONTEXT_TYPE $CONTEXT_NAME'
result = client.query(sql)

if result['success']:
    print(f'✓ Switched $CONTEXT_TYPE to $CONTEXT_NAME')
else:
    print(f'Error: {result[\"error\"]}', file=sys.stderr)
    exit(1)
" "$@"
```
```

**Integration Test:**

21. **`tests/test_session_integration.py`**
```python
import pytest
from daemon.client import DaemonClient

@pytest.mark.integration
def test_session_persistence():
    """Test that context persists across queries."""
    client = DaemonClient()

    # Switch database
    result = client.query("USE DATABASE CLAUDE_DB")
    assert result['success']

    # Verify context changed
    result = client.query("SELECT CURRENT_DATABASE()")
    assert result['data'][0][0] == "CLAUDE_DB"

    # Execute query without specifying database
    result = client.query("SHOW TABLES")
    assert result['success']
    # Tables should be from CLAUDE_DB context
```

**Success Criteria:**
- [ ] `/sf-use` command switches context
- [ ] Context persists for subsequent queries
- [ ] Integration test passes with real Snowflake
- [ ] No need to specify database in every query

---

### Phase 3: Connection Pool & Reliability (Week 3)

**Goal:** Implement connection pooling, health monitoring, auto-reconnect

#### Milestone 3.1: Connection Pool (Day 12-14)

**Files to create:**

22. **`daemon/connection_pool.py`** - Connection pool manager
```python
from typing import Dict, Optional
import asyncio
from daemon.connection import SnowflakeConnection
from daemon.state import StateManager
import structlog

logger = structlog.get_logger()

class ConnectionPool:
    """Manages pool of Snowflake connections."""

    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self.connections: Dict[int, SnowflakeConnection] = {}
        self.state_managers: Dict[int, StateManager] = {}
        self.lock = asyncio.Lock()
        self._next_id = 0

    async def get_connection(self) -> tuple[int, SnowflakeConnection, StateManager]:
        """Get or create a connection from the pool."""
        async with self.lock:
            # Reuse existing healthy connection
            for conn_id, conn in self.connections.items():
                if conn.is_healthy():
                    logger.info("reusing_connection", conn_id=conn_id)
                    return conn_id, conn, self.state_managers[conn_id]

            # Create new connection if under limit
            if len(self.connections) < self.max_size:
                conn_id = self._next_id
                self._next_id += 1

                conn = SnowflakeConnection()
                state_manager = StateManager()

                self.connections[conn_id] = conn
                self.state_managers[conn_id] = state_manager

                logger.info("created_connection", conn_id=conn_id)
                return conn_id, conn, state_manager

            # Pool full, return first connection (could improve with LRU)
            conn_id = list(self.connections.keys())[0]
            return conn_id, self.connections[conn_id], self.state_managers[conn_id]

    async def health_check(self):
        """Check health of all connections and remove unhealthy ones."""
        async with self.lock:
            unhealthy = []
            for conn_id, conn in self.connections.items():
                if not conn.is_healthy():
                    logger.warning("unhealthy_connection", conn_id=conn_id)
                    unhealthy.append(conn_id)

            for conn_id in unhealthy:
                self.connections[conn_id].close()
                del self.connections[conn_id]
                del self.state_managers[conn_id]

    async def close_all(self):
        """Close all connections in the pool."""
        async with self.lock:
            for conn in self.connections.values():
                conn.close()
            self.connections.clear()
            self.state_managers.clear()
```

23. **Update `daemon/server.py`** - Use connection pool
```python
from daemon.connection_pool import ConnectionPool

# Global connection pool
connection_pool = ConnectionPool(max_size=3)

@app.post("/query")
async def execute_query(request: QueryRequest) -> QueryResponse:
    conn_id, connection, state_manager = await connection_pool.get_connection()
    executor = QueryExecutor(connection, state_manager)
    response = await executor.execute(request.sql, request.limit)
    return response

@app.on_event("startup")
async def startup():
    logger.info("daemon_starting")

@app.on_event("shutdown")
async def shutdown():
    await connection_pool.close_all()
    logger.info("daemon_stopped")
```

**Unit Tests:**

24. **`tests/test_connection_pool.py`**
```python
import pytest
from daemon.connection_pool import ConnectionPool

@pytest.mark.asyncio
async def test_pool_creates_new_connection_when_empty():
    pool = ConnectionPool(max_size=3)
    conn_id, conn, state = await pool.get_connection()
    assert conn_id == 0
    assert conn is not None
    assert state is not None

@pytest.mark.asyncio
async def test_pool_reuses_healthy_connection():
    pool = ConnectionPool(max_size=3)

    # Get first connection
    conn_id1, conn1, _ = await pool.get_connection()

    # Get second connection (should reuse)
    conn_id2, conn2, _ = await pool.get_connection()

    # Should be the same connection
    assert conn_id1 == conn_id2
    assert conn1 is conn2

@pytest.mark.asyncio
async def test_pool_respects_max_size():
    pool = ConnectionPool(max_size=2)

    # Mock unhealthy connections to force creation
    # ... test that max 2 connections are created
    pass
```

**Success Criteria:**
- [ ] Pool creates connections on demand
- [ ] Pool reuses healthy connections
- [ ] Pool respects max size
- [ ] Unhealthy connections are removed
- [ ] Unit tests pass

---

#### Milestone 3.2: Auto-Reconnect & Health Monitoring (Day 15-16)

**Files to create:**

25. **`daemon/health.py`** - Health monitoring
```python
import asyncio
from daemon.connection_pool import ConnectionPool
import structlog

logger = structlog.get_logger()

class HealthMonitor:
    """Background task to monitor connection health."""

    def __init__(self, connection_pool: ConnectionPool, check_interval: int = 60):
        self.connection_pool = connection_pool
        self.check_interval = check_interval
        self._task: Optional[asyncio.Task] = None

    async def _monitor_loop(self):
        """Periodic health check loop."""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                logger.info("running_health_check")
                await self.connection_pool.health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_failed", error=str(e))

    def start(self):
        """Start health monitoring."""
        if self._task is None:
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("health_monitor_started")

    def stop(self):
        """Stop health monitoring."""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("health_monitor_stopped")
```

26. **Update `daemon/connection.py`** - Add reconnect logic
```python
def connect(self, reconnect: bool = True) -> snowflake.connector.SnowflakeConnection:
    """Establish connection to Snowflake with auto-reconnect."""
    max_retries = 3 if reconnect else 1

    for attempt in range(max_retries):
        try:
            if self._connection is None or self._connection.is_closed():
                self._connection = snowflake.connector.connect(
                    account=self.account,
                    user=self.user,
                    password=self.password,
                    warehouse=self.warehouse,
                    database=self.database,
                    schema=self.schema,
                    role=self.role
                )
            return self._connection
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"connection_attempt_failed", attempt=attempt+1, error=str(e))
            time.sleep(2 ** attempt)  # Exponential backoff
```

27. **Update `daemon/server.py`** - Start health monitor
```python
from daemon.health import HealthMonitor

health_monitor = HealthMonitor(connection_pool, check_interval=60)

@app.on_event("startup")
async def startup():
    health_monitor.start()
    logger.info("daemon_started")
```

**Success Criteria:**
- [ ] Connections auto-reconnect on failure
- [ ] Health monitor runs in background
- [ ] Unhealthy connections are replaced
- [ ] Daemon remains responsive during reconnect

---

### Phase 4: Write Operations & Transactions (Week 4)

**Goal:** Add DML/DDL support with transaction management

#### Milestone 4.1: Validator Integration (Day 17-18)

**Files to copy from original plugin:**

28. Copy **`validators.py`** from original plugin
   - Reuse ReadOnlyValidator, DMLValidator, DDLValidator, WriteValidator

29. **Update `daemon/executor.py`** - Use validators
```python
from validators import WriteValidator

class QueryExecutor:
    def __init__(self, connection: SnowflakeConnection, state_manager: StateManager):
        self.connection = connection
        self.state_manager = state_manager
        self.validator = WriteValidator()  # Supports all operations

    def _validate_query(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate query using pluggable validators."""
        return self.validator.validate(sql)
```

**Success Criteria:**
- [ ] Validators integrated from original plugin
- [ ] Read-only queries still work
- [ ] DML/DDL queries validated correctly

---

#### Milestone 4.2: Transaction Support (Day 19-20)

**Files to create:**

30. **`daemon/models.py`** - Add transaction models
```python
class WriteRequest(BaseModel):
    sql: str
    use_transaction: bool = True
    skip_confirmation: bool = False

class WriteResponse(BaseModel):
    success: bool
    rows_affected: Optional[int] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
```

31. **Update `daemon/executor.py`** - Add write execution
```python
async def execute_write(
    self,
    sql: str,
    use_transaction: bool = True
) -> WriteResponse:
    """Execute write operation with transaction support."""
    start_time = time.time()

    # Validate
    is_valid, error = self._validate_query(sql)
    if not is_valid:
        return WriteResponse(success=False, error=error)

    try:
        conn = self.connection.connect()
        cursor = conn.cursor()

        if use_transaction:
            cursor.execute("BEGIN")

        try:
            cursor.execute(sql)
            rows_affected = cursor.rowcount

            if use_transaction:
                cursor.execute("COMMIT")

            cursor.close()
            execution_time = time.time() - start_time

            return WriteResponse(
                success=True,
                rows_affected=rows_affected,
                execution_time=execution_time
            )
        except Exception as e:
            if use_transaction:
                cursor.execute("ROLLBACK")
            raise e

    except Exception as e:
        execution_time = time.time() - start_time
        return WriteResponse(
            success=False,
            error=str(e),
            execution_time=execution_time
        )
```

32. **Add `/write` endpoint to `daemon/server.py`**
```python
@app.post("/write")
async def execute_write(request: WriteRequest) -> WriteResponse:
    conn_id, connection, state_manager = await connection_pool.get_connection()
    executor = QueryExecutor(connection, state_manager)
    response = await executor.execute_write(
        request.sql,
        request.use_transaction
    )
    return response
```

33. **`commands/sf-write.md`** - Write command
```markdown
---
description: Execute DML operations (INSERT, UPDATE, DELETE, MERGE)
---

# Snowflake Write Operations

Execute data modification operations with transaction support.

## Usage

```bash
/snowflake-daemon:sf-write <sql>
```

## Examples

```bash
/snowflake-daemon:sf-write INSERT INTO customers (name, email) VALUES ('Alice', 'alice@example.com')
/snowflake-daemon:sf-write UPDATE products SET price = price * 1.1 WHERE category = 'electronics'
/snowflake-daemon:sf-write DELETE FROM logs WHERE created_at < CURRENT_DATE - 90
```

## Implementation

```bash
#!/bin/bash
python -c "
from daemon.client import DaemonClient

client = DaemonClient()
result = client.write('''$1''')

if result['success']:
    print(f\"✓ Success: {result['rows_affected']} rows affected\")
else:
    print(f\"Error: {result['error']}\", file=sys.stderr)
    exit(1)
" "$@"
```
```

**Success Criteria:**
- [ ] DML operations execute successfully
- [ ] Transactions auto-commit on success
- [ ] Transactions auto-rollback on error
- [ ] Rows affected reported correctly

---

### Phase 5: Polish & Production Readiness (Week 5)

#### Milestone 5.1: Result Formatting (Day 21-22)

**Files to copy:**

34. Copy **`formatters.py`** from original plugin
   - format_as_table, format_as_json, format_as_csv

35. **Update `daemon/executor.py`** - Add formatting
```python
from formatters import format_result

async def execute(self, sql: str, limit: Optional[int] = 100, format: str = "table") -> QueryResponse:
    # ... execute query ...

    # Format results
    formatted = format_result(rows, columns, format)

    return QueryResponse(
        success=True,
        data=rows,
        columns=columns,
        row_count=len(rows),
        formatted=formatted,
        execution_time=execution_time
    )
```

36. **Update commands to use formatting**

**Success Criteria:**
- [ ] Results formatted as tables
- [ ] JSON format available
- [ ] CSV format available

---

#### Milestone 5.2: Error Handling Enhancement (Day 23-24)

**Files to copy:**

37. Copy **`errors.py`** from original plugin

38. **Update `daemon/executor.py`** - Enhance errors
```python
from errors import enhance_error_message

async def execute(self, sql: str, ...) -> QueryResponse:
    try:
        # ... execute ...
    except Exception as e:
        enhanced_error = enhance_error_message(str(e), sql)
        return QueryResponse(
            success=False,
            error=enhanced_error,
            execution_time=execution_time
        )
```

**Success Criteria:**
- [ ] Error messages enhanced with hints
- [ ] Context-aware suggestions
- [ ] Helpful error messages for common issues

---

#### Milestone 5.3: Daemon Lifecycle Management (Day 25-26)

**Files to create:**

39. **`daemon/lifecycle.py`** - Auto-shutdown on idle
```python
import asyncio
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class IdleShutdownManager:
    """Auto-shutdown daemon after idle period."""

    def __init__(self, idle_timeout: int = 1800):  # 30 minutes
        self.idle_timeout = idle_timeout
        self.last_activity = datetime.now()
        self._task: Optional[asyncio.Task] = None

    def record_activity(self):
        """Record activity to reset idle timer."""
        self.last_activity = datetime.now()

    async def _monitor_loop(self):
        """Check for idle timeout."""
        while True:
            await asyncio.sleep(60)  # Check every minute

            idle_seconds = (datetime.now() - self.last_activity).total_seconds()

            if idle_seconds > self.idle_timeout:
                logger.info("idle_timeout_shutdown", idle_seconds=idle_seconds)
                # Trigger graceful shutdown
                os.kill(os.getpid(), signal.SIGTERM)
                break

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("idle_monitor_started")
```

40. **Update `daemon/server.py`** - Track activity
```python
from daemon.lifecycle import IdleShutdownManager

idle_manager = IdleShutdownManager(idle_timeout=1800)

@app.middleware("http")
async def track_activity(request: Request, call_next):
    idle_manager.record_activity()
    response = await call_next(request)
    return response

@app.on_event("startup")
async def startup():
    health_monitor.start()
    idle_manager.start()
```

**Success Criteria:**
- [ ] Daemon auto-shuts down after 30 minutes idle
- [ ] Activity resets idle timer
- [ ] Graceful shutdown on timeout

---

#### Milestone 5.4: Documentation & Examples (Day 27-28)

41. **`README.md`** - Complete documentation
```markdown
# Snowflake Daemon Plugin

Session-persistent Snowflake plugin with background daemon for maintaining database connections.

## Features
- Persistent connections (context persists across queries)
- Connection pooling
- Auto-reconnect on failure
- Transaction support
- Health monitoring
- Auto-shutdown on idle

## Installation
[Setup instructions]

## Usage
[Command examples]

## Architecture
[Daemon architecture diagram]
```

42. **`HANDOFF.md`** - Implementation guide (this document)

**Success Criteria:**
- [ ] README complete with examples
- [ ] Installation instructions tested
- [ ] Architecture documented
- [ ] Troubleshooting guide included

---

## Testing Strategy

### Unit Tests (Throughout Implementation)

Run after each milestone:
```bash
pytest tests/ -v --cov=daemon --cov-report=html
```

Target: 80%+ code coverage

### Integration Tests (Phase 2+)

Require real Snowflake account:
```bash
pytest tests/ -m integration -v
```

Test scenarios:
- Session persistence across queries
- Connection pool under load
- Transaction rollback on error
- Health monitoring and reconnect

### Manual Testing (Phase 5)

```bash
# Start daemon manually
python -m uvicorn daemon.server:app --host 127.0.0.1 --port 8765

# Test with commands
/sf-connect
/sf-query SELECT 1
/sf-use database MY_DB
/sf-query SHOW TABLES
```

---

## Deployment & Distribution

### Local Development

```bash
# Install in development mode
pip install -e .

# Run daemon
python -m uvicorn daemon.server:app --reload

# Test plugin
claude --plugin-dir .
```

### Distribution

Package as Claude Code plugin:
```bash
# Create plugin package
tar -czf snowflake-daemon-plugin.tar.gz \
  .claude-plugin/ \
  commands/ \
  daemon/ \
  requirements.txt \
  README.md

# Users install with
claude plugin install snowflake-daemon-plugin.tar.gz
```

---

## Success Metrics

### Phase 1 Success Criteria
- [ ] Daemon starts and accepts requests
- [ ] Basic query execution works
- [ ] Commands communicate with daemon
- [ ] Unit tests pass (>80% coverage)

### Phase 2 Success Criteria
- [ ] Session state persists across queries
- [ ] USE commands work correctly
- [ ] Integration tests pass

### Phase 3 Success Criteria
- [ ] Connection pool manages 3+ connections
- [ ] Auto-reconnect on connection failure
- [ ] Health monitoring detects issues

### Phase 4 Success Criteria
- [ ] DML operations work with transactions
- [ ] DDL operations work
- [ ] Transaction rollback on error

### Phase 5 Success Criteria
- [ ] Production-ready error handling
- [ ] Auto-shutdown on idle
- [ ] Complete documentation
- [ ] Ready for distribution

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Daemon crashes | Health monitoring, auto-restart, graceful error handling |
| Connection loss | Auto-reconnect with exponential backoff |
| Memory leaks | Connection pool size limit, idle shutdown |
| Port conflicts | Configurable port, check before start |
| Concurrent access | Connection pool with locking |
| Credential exposure | Environment variables, never log credentials |

---

## File Inventory

**Core Daemon:**
- `daemon/server.py` - FastAPI server (100 lines)
- `daemon/models.py` - Request/response models (50 lines)
- `daemon/connection.py` - Connection manager (150 lines)
- `daemon/connection_pool.py` - Pool manager (100 lines)
- `daemon/executor.py` - Query executor (200 lines)
- `daemon/state.py` - Session state (80 lines)
- `daemon/health.py` - Health monitoring (80 lines)
- `daemon/lifecycle.py` - Idle shutdown (60 lines)
- `daemon/client.py` - HTTP client (80 lines)

**Reused from Original:**
- `validators.py` - Query validators (267 lines)
- `formatters.py` - Result formatters (99 lines)
- `errors.py` - Error enhancement (192 lines)

**Plugin Interface:**
- `commands/sf-query.md` - Query command
- `commands/sf-write.md` - Write command
- `commands/sf-connect.md` - Connection test
- `commands/sf-context.md` - Show context
- `commands/sf-use.md` - Switch context
- `.claude-plugin/plugin.json` - Manifest

**Testing:**
- `tests/test_daemon.py`
- `tests/test_connection.py`
- `tests/test_executor.py`
- `tests/test_connection_pool.py`
- `tests/test_state.py`
- `tests/test_session_integration.py`

**Documentation:**
- `README.md` - User documentation
- `HANDOFF.md` - Implementation guide (this file)
- `.env.example` - Configuration template

**Total Estimated Lines:** ~1,500 new + ~560 reused = ~2,060 lines

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | Week 1 | Basic daemon with query execution |
| Phase 2 | Week 2 | Session management with USE commands |
| Phase 3 | Week 3 | Connection pool and reliability |
| Phase 4 | Week 4 | Write operations and transactions |
| Phase 5 | Week 5 | Polish and production readiness |

**Total:** 5 weeks for production-ready daemon plugin

---

## Next Steps

1. Create new project directory
2. Set up Python environment
3. Start with Phase 1, Milestone 1.1 (Project Setup)
4. Write tests before implementation (TDD)
5. Commit after each milestone
6. Review and iterate

**Ready to begin implementation!**
