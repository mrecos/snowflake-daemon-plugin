# Snowflake Daemon Plugin

Session-persistent Snowflake plugin with background daemon for maintaining database connections.

## Overview

This Claude Code plugin provides a **stateful Snowflake connection** using a lightweight Python daemon that maintains persistent database connections. This solves the critical limitation where each command created a new connection, preventing context (database/schema/warehouse) from persisting.

## Key Features

- **Persistent Connections**: Background daemon maintains connection pool
- **Session State**: Database, schema, warehouse, and role persist across queries
- **Auto-Start**: Daemon automatically starts on first command
- **Auto-Shutdown**: Gracefully shuts down after idle timeout (default 30 minutes)
- **Connection Pooling**: Manages multiple connections with health monitoring
- **Transaction Support**: DML operations with automatic commit/rollback

## Architecture

```
Claude Code Plugin (commands/skills)
        ↓ (HTTP/Socket)
Lightweight Python Daemon (FastAPI)
        ↓ (persistent connection)
    Snowflake Database
```

## Installation

### 1. Clone the repository

```bash
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

## Development Status

This project is currently in **Phase 1: Foundation**.

### Completed Milestones

- [x] Phase 1, Milestone 1.1: Project Setup
  - [x] FastAPI server starts on localhost:8765
  - [x] `/health` endpoint returns 200
  - [x] `/query` endpoint accepts requests
  - [x] Unit tests structure in place

### Next Steps

- [ ] Phase 1, Milestone 1.2: Connection Manager
- [ ] Phase 1, Milestone 1.3: Basic Query Execution
- [ ] Phase 1, Milestone 1.4: Plugin Commands

See [HANDOFF.md](HANDOFF.md) for the complete implementation plan.

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ -v --cov=daemon --cov-report=html
```

## Manual Testing

Start the daemon manually:

```bash
python -m uvicorn daemon.server:app --host 127.0.0.1 --port 8765
```

Test the health endpoint:

```bash
curl http://127.0.0.1:8765/health
```

## Project Structure

```
snowflake-daemon-plugin/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── daemon/
│   ├── __init__.py
│   ├── server.py            # FastAPI server
│   └── models.py            # Pydantic models
├── commands/                # Plugin commands (TBD)
├── tests/
│   ├── __init__.py
│   └── test_daemon.py       # Unit tests
├── .env.example             # Configuration template
├── .gitignore
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── HANDOFF.md              # Implementation guide
└── README.md               # This file
```

## License

MIT

## Author

Matt Harris
