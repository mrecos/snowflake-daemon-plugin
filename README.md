# Snowflake Claude-Code Plugin 

## (Not an official product of Snowflake or Anthropic)

![Snowflake Daemon Plugin banner](img/banner1.png)

Session-persistent Snowflake plugin with background daemon for maintaining database connections.

## Overview

This Claude Code plugin provides a **stateful Snowflake connection** using a lightweight Python daemon that maintains persistent database connections. This solves the critical limitation where each command created a new connection, preventing context (database/schema/warehouse) from persisting.

## Key Features

- **Persistent Connections**: Background daemon maintains persistent connection
- **Session State**: Database, schema, warehouse, and role persist across queries
- **Full SQL Support**: All operations (read, DML, DDL, transactions)
- **Enhanced Error Messages**: Context-aware hints and suggestions for common errors
- **Auto-Start**: Daemon automatically starts on first command
- **Graceful Shutdown**: Stop daemon and auto-restart on next query
- **Auto-Reconnect**: Handles authentication token expiry transparently
- **Flexible Security**: Configurable validators (read-only, DML, DDL, or full access)

## Architecture

```
Claude Code Plugin (commands/skills)
        ↓ (HTTP/Socket)
Lightweight Python Daemon (FastAPI)
        ↓ (persistent connection)
    Snowflake Database
```

## Installation

### 1. Install the plugin in Claude Code

The plugin must be installed in your Claude Code plugins directory:

```bash
# Navigate to your Claude Code plugins directory
cd ~/.config/claude/plugins  # Linux/macOS
# or
cd %APPDATA%\claude\plugins  # Windows

# Clone the repository
git clone https://github.com/mrecos/snowflake-daemon-plugin.git
cd snowflake-daemon-plugin
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

### 3. Configure credentials

Copy `.env.example` to `.env` and fill in your Snowflake credentials:

```bash
cp .env.example .env
```

Edit `.env` with your Snowflake account details:
```
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PAT=your_personal_access_token
```

### 4. Restart Claude Code

Restart Claude Code to load the plugin. You can verify it's installed by typing `/` in Claude Code and looking for `snowflake-daemon` commands.

## Usage

The plugin provides slash commands in Claude Code for interacting with Snowflake through the persistent daemon.

### Quick Start

In Claude Code, simply type `/` to see available commands, or just tell Claude what you want to do:

```
"Show me the tables in my database"
"Query the customers table"
"What's my current database and schema?"
"Stop the Snowflake daemon"
```

Claude Code will automatically select the appropriate slash command based on your intent.

### Available Commands

### Test Connection

```
/snowflake-daemon:sf-connect
```

Tests the daemon connection and displays Snowflake connection info:

**Example output:**
```
✓ Daemon is running
  Status: healthy
  Connection count: 1
  Uptime: 5.2s

✓ Connected to Snowflake
  Version: 8.45.0
  User: YOUR_USERNAME
  Role: YOUR_ROLE
  Database: YOUR_DATABASE
  Schema: YOUR_SCHEMA
  Warehouse: YOUR_WAREHOUSE
```

### Execute Queries

```
/snowflake-daemon:sf-query "SELECT * FROM my_table"
```

Execute SQL queries with optional row limit (default: 100).

**Supported query types:**

**Read Operations:**
- `SELECT` - Query data
- `SHOW` - Show database objects
- `DESCRIBE` / `DESC` - Describe table structure
- `WITH` - Common table expressions
- `USE` - Change context (database, schema, warehouse, role)

**Write Operations (DML):**
- `INSERT` - Insert data
- `UPDATE` - Update data
- `DELETE` - Delete data
- `MERGE` - Merge data
- `COPY` - Load data from stages

**DDL Operations:**
- `CREATE` - Create tables, views, etc.
- `DROP` - Drop tables, views, etc.
- `ALTER` - Modify table structure
- `TRUNCATE` - Clear table data

**Example queries:**

```
# Read operations
/snowflake-daemon:sf-query "SELECT * FROM customers LIMIT 10"
/snowflake-daemon:sf-query "SHOW TABLES"
/snowflake-daemon:sf-query "USE DATABASE my_db"

# Write operations (DML)
/snowflake-daemon:sf-query "INSERT INTO customers (name, email) VALUES ('Alice', 'alice@example.com')"
/snowflake-daemon:sf-query "UPDATE customers SET status = 'active' WHERE id = 1"
/snowflake-daemon:sf-query "DELETE FROM customers WHERE id = 999"

# DDL operations
/snowflake-daemon:sf-query "CREATE TABLE test (id INT, name VARCHAR(100))"
/snowflake-daemon:sf-query "ALTER TABLE test ADD COLUMN email VARCHAR(200)"
/snowflake-daemon:sf-query "DROP TABLE test"
```

**Example output:**
```
| ID | NAME |
| --- | --- |
| 1 | Alice |
| 2 | Bob |

✓ 2 row(s) in 0.234s
```

**Note:**
- All SQL operations are supported (read, DML, and DDL)
- Query results are formatted as markdown tables for better readability
- In Claude Code, tool output may be collapsed by default - press `Ctrl+O` (or `Cmd+O` on Mac) to expand and view the full table
- **Use caution with write operations** - changes are immediately committed to Snowflake

### Check Session Context

```
/snowflake-daemon:sf-context
```

Display current session state (database, schema, warehouse, role).

**Example output:**
```
Current Snowflake Session Context:
  Database:  CLAUDE_DB
  Schema:    PUBLIC
  Warehouse: COMPUTE_WH
  Role:      ACCOUNTADMIN
```

### Stop Daemon

```
/snowflake-daemon:sf-stop
```

Gracefully stop the daemon and close the Snowflake connection.

**Use cases:**
- Load new code changes (daemon restarts with updated code)
- Free resources when not actively querying
- Force new connection on next query
- Reset daemon state

**Example output:**
```
Stopping Snowflake daemon...
✓ Daemon shutdown initiated

The daemon will:
  - Close Snowflake connection
  - Release resources
  - Auto-restart on next query
```

The daemon will automatically restart on the next query command.

### Command Features

- **Auto-start**: Daemon starts automatically on first command use
- **Persistent connection**: Connection and context preserved across queries
- **Full SQL support**: All operations supported (read, DML, DDL)
- **Auto-LIMIT**: SELECT queries automatically get LIMIT clause
- **Enhanced error messages**: Context-aware hints and suggestions for common errors
- **No manual setup**: Just use the slash commands - they handle everything
- **Claude Code integration**: Commands auto-selected based on user intent
- **Flexible security**: Configurable validators (ReadOnly, DML, DDL, or Write-all)

## Development Status

This project has completed **Phase 1 (Foundation)**, **Phase 2 (Session Management)**, **Phase 4.1 (Write Operations)**, and **Phase 5.2 (Error Enhancement)**.

### Completed Milestones

- [x] **Phase 1, Milestone 1.1: Project Setup**
  - [x] FastAPI server starts on localhost:8765
  - [x] `/health` endpoint returns 200
  - [x] `/query` endpoint accepts requests
  - [x] Unit tests structure in place

- [x] **Phase 1, Milestone 1.2: Connection Manager**
  - [x] SnowflakeConnection class with PAT authentication
  - [x] Connection validation and health checks
  - [x] 13 comprehensive unit tests
  - [x] 100% code coverage on connection module

- [x] **Phase 1, Milestone 1.3: Basic Query Execution**
  - [x] QueryExecutor with read-only query validation
  - [x] Automatic LIMIT clause addition for SELECT queries
  - [x] Structured query results with columns and metadata
  - [x] 24 comprehensive unit tests
  - [x] 93% overall code coverage

- [x] **Phase 1, Milestone 1.4: Plugin Commands**
  - [x] DaemonClient for HTTP communication with daemon
  - [x] Auto-start daemon on first command
  - [x] `/snowflake-daemon:sf-connect` - Test connection
  - [x] `/snowflake-daemon:sf-query` - Execute queries
  - [x] 17 comprehensive unit tests for client
  - [x] 95% overall code coverage

- [x] **Phase 2, Milestone 2.1: Session State Management**
  - [x] StateManager class for tracking session context
  - [x] USE command support (DATABASE, SCHEMA, WAREHOUSE, ROLE)
  - [x] `/snowflake-daemon:sf-context` - Display current context
  - [x] `/snowflake-daemon:sf-stop` - Graceful daemon shutdown
  - [x] Auto-reconnect on authentication token expiry
  - [x] 18 comprehensive unit tests for state manager
  - [x] 86% overall code coverage

- [x] **Phase 4, Milestone 4.1: Validator Integration & Write Operations**
  - [x] Pluggable validator architecture (BaseValidator, ReadOnlyValidator, DMLValidator, DDLValidator, WriteValidator)
  - [x] Support for all SQL operations (read, DML, DDL, transactions)
  - [x] INSERT, UPDATE, DELETE, MERGE, COPY operations
  - [x] CREATE, DROP, ALTER, TRUNCATE operations
  - [x] Transaction control (BEGIN, COMMIT, ROLLBACK)
  - [x] 55 comprehensive validator tests
  - [x] End-to-end testing with real Snowflake
  - [x] Configurable security levels

- [x] **Phase 5, Milestone 5.2: Error Handling Enhancement**
  - [x] Enhanced error messages with context-aware hints
  - [x] Pattern matching for common Snowflake errors
  - [x] Helpful suggestions for object not found errors
  - [x] Database/schema/warehouse context hints
  - [x] Syntax error guidance
  - [x] Permission error suggestions
  - [x] SQL query context in error output
  - [x] 34 comprehensive error enhancement tests
  - [x] Retriable error detection

### Test Results

```
✅ 163 total tests passing (74 base + 55 validator + 34 error tests)
✅ All write operations tested and working
✅ Enhanced error messages providing helpful guidance
✅ Production-ready with full SQL support
```

### Next Steps

- [ ] Phase 3: Connection Pool & Reliability
- [ ] Phase 4, Milestone 4.2: Transaction Support (explicit transactions)
- [ ] Phase 5: Polish & Production Readiness

See [HANDOFF.md](HANDOFF.md) for the complete implementation plan.

## Testing

### Unit Tests

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ -v --cov=daemon --cov-report=html
```

### Integration Testing with Real Snowflake

To test the daemon with a real Snowflake connection, see the comprehensive guide:

**[INTEGRATION_TEST.md](INTEGRATION_TEST.md)** - Complete integration testing guide

Quick start:

1. Configure `.env` with your Snowflake credentials
2. Start the daemon: `python -m uvicorn daemon.server:app --host 127.0.0.1 --port 8765`
3. Test health: `curl http://127.0.0.1:8765/health`
4. Test a query: `curl -X POST http://127.0.0.1:8765/query -H "Content-Type: application/json" -d '{"sql": "SELECT 1"}'`

See [INTEGRATION_TEST.md](INTEGRATION_TEST.md) for detailed testing instructions.

## Project Structure

```
snowflake-daemon-plugin/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── daemon/
│   ├── __init__.py
│   ├── server.py            # FastAPI server with endpoints
│   ├── models.py            # Pydantic request/response models
│   ├── connection.py        # Snowflake connection manager
│   ├── executor.py          # Query executor with validation
│   ├── state.py             # Session state manager
│   └── client.py            # HTTP client for daemon communication
├── commands/
│   ├── sf-connect.md        # Connection test command
│   ├── sf-query.md          # Query execution command
│   ├── sf-context.md        # Session context command
│   └── sf-stop.md           # Daemon shutdown command
├── bin/
│   ├── sf-connect           # Executable: test connection
│   ├── sf-query             # Executable: execute queries
│   ├── sf-context           # Executable: show session state
│   └── sf-stop              # Executable: stop daemon
├── tests/
│   ├── __init__.py
│   ├── test_daemon.py       # Daemon/server tests
│   ├── test_connection.py   # Connection manager tests
│   ├── test_executor.py     # Query executor tests
│   └── test_client.py       # Client tests
├── .env.example             # Configuration template
├── .gitignore
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── HANDOFF.md              # Implementation guide
├── INTEGRATION_TEST.md     # Integration testing guide
└── README.md               # This file
```

## License

MIT

## Author

Matt Harris
