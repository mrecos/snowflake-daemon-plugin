# Integration Testing Guide - Snowflake Daemon Plugin

This guide will help you test the daemon with a real Snowflake connection after completing Phase 1, Milestone 1.3.

## Prerequisites

- Python 3.10+ installed
- Access to a Snowflake account
- Snowflake Personal Access Token (PAT) or password

## Step 1: Configure Credentials

### 1.1 Create `.env` file

Copy the example configuration and fill in your Snowflake credentials:

```bash
cp .env.example .env
```

### 1.2 Edit `.env` with your credentials

Open `.env` in your editor and fill in the required fields:

```bash
# Required credentials
SNOWFLAKE_ACCOUNT=your_account_identifier    # e.g., abc12345.us-east-1
SNOWFLAKE_USER=your_username                 # Your Snowflake username
SNOWFLAKE_PAT=your_personal_access_token     # Your PAT or password

# Optional: Default context (recommended for testing)
SNOWFLAKE_WAREHOUSE=COMPUTE_WH               # A warehouse you have access to
SNOWFLAKE_DATABASE=your_database             # A database to query
SNOWFLAKE_SCHEMA=your_schema                 # A schema in that database
SNOWFLAKE_ROLE=your_role                     # Your role (e.g., ACCOUNTADMIN)
```

**Finding your account identifier:**
- Log into Snowflake web UI
- Look at the URL: `https://<account_identifier>.snowflakecomputing.com`
- Use the `<account_identifier>` part (e.g., `abc12345.us-east-1`)

**Creating a Personal Access Token:**
1. In Snowflake web UI, click your name in top right
2. Go to "My Profile" → "Password & Authentication"
3. Under "Personal Access Tokens", click "Generate Token"
4. Copy the token immediately (you won't see it again)

### 1.3 Verify `.env` is gitignored

**Important:** Ensure your `.env` file is never committed to git:

```bash
# Verify .env is in .gitignore
grep "^\.env$" .gitignore

# Check git status (should NOT show .env)
git status
```

## Step 2: Install Dependencies

Install all required packages:

```bash
pip install -r requirements.txt
```

## Step 3: Start the Daemon

### 3.1 Start daemon manually

```bash
python -m uvicorn daemon.server:app --host 127.0.0.1 --port 8765
```

You should see output like:

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
```

**If you see an error about missing credentials**, verify your `.env` file is correctly configured.

### 3.2 Keep daemon running

Leave this terminal window open with the daemon running. Open a new terminal for the next steps.

## Step 4: Test the Health Endpoint

### 4.1 Using curl

```bash
curl http://127.0.0.1:8765/health
```

**Expected output:**

```json
{
  "status": "healthy",
  "uptime_seconds": 5.123,
  "connection_count": 1,
  "active_queries": 0
}
```

**Status meanings:**
- `healthy`: Daemon started successfully with valid credentials
- `degraded`: Daemon started but credentials are missing or invalid
- `unhealthy`: Daemon is experiencing issues

### 4.2 Using Python

```python
import httpx

response = httpx.get("http://127.0.0.1:8765/health")
print(response.json())
```

## Step 5: Test Basic Query Execution

### 5.1 Simple SELECT query

Test with a simple query that should work in any Snowflake account:

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT CURRENT_VERSION() as version, CURRENT_USER() as user, CURRENT_ROLE() as role",
    "limit": 10
  }'
```

**Expected output:**

```json
{
  "success": true,
  "data": [
    ["8.45.0", "YOUR_USERNAME", "YOUR_ROLE"]
  ],
  "columns": ["VERSION", "USER", "ROLE"],
  "row_count": 1,
  "formatted": null,
  "error": null,
  "execution_time": 0.234
}
```

### 5.2 SHOW commands

Test SHOW commands (no LIMIT added):

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SHOW WAREHOUSES"
  }'
```

### 5.3 Query with LIMIT

Test that automatic LIMIT is added:

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM INFORMATION_SCHEMA.TABLES",
    "limit": 5
  }'
```

The query will automatically have `LIMIT 5` added.

### 5.4 Query your own data

If you configured a database and schema in `.env`:

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SHOW TABLES"
  }'
```

## Step 6: Test Query Validation (Read-Only)

### 6.1 Test that write operations are blocked

Try an INSERT (should fail):

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "INSERT INTO test_table VALUES (1)"
  }'
```

**Expected output:**

```json
{
  "success": false,
  "data": null,
  "columns": null,
  "row_count": null,
  "formatted": null,
  "error": "Only read-only queries allowed: INSERT",
  "execution_time": null
}
```

### 6.2 Other blocked operations

These should all fail with read-only error:

```bash
# UPDATE
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "UPDATE test SET col=1"}'

# DELETE
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "DELETE FROM test"}'

# CREATE
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "CREATE TABLE test (id INT)"}'

# DROP
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "DROP TABLE test"}'
```

## Step 7: Test Error Handling

### 7.1 Invalid SQL syntax

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM nonexistent_table_xyz"
  }'
```

**Expected:** Error message from Snowflake about table not existing.

### 7.2 Permission error

Try to access a database you don't have access to:

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM RESTRICTED_DATABASE.SCHEMA.TABLE"
  }'
```

## Step 8: Test Connection Health

### 8.1 Verify connection is active

After running some queries, check health again:

```bash
curl http://127.0.0.1:8765/health
```

The `connection_count` should be 1 if the connection is healthy.

### 8.2 Using Python for comprehensive test

```python
import httpx

# Test health
health = httpx.get("http://127.0.0.1:8765/health")
print("Health:", health.json())

# Test simple query
query_response = httpx.post(
    "http://127.0.0.1:8765/query",
    json={"sql": "SELECT 1 as test_col", "limit": 1}
)
result = query_response.json()

print("\nQuery Success:", result["success"])
print("Data:", result["data"])
print("Columns:", result["columns"])
print("Execution Time:", result["execution_time"], "seconds")
```

## Step 9: Performance Testing (Optional)

Test query execution time for a more complex query:

```bash
curl -X POST http://127.0.0.1:8765/query \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES",
    "limit": 1
  }'
```

Check the `execution_time` in the response.

## Troubleshooting

### Issue: "Missing required env vars"

**Solution:** Check your `.env` file has all required fields:
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PAT`

### Issue: "Connection refused" when calling endpoints

**Solution:** Ensure the daemon is running:
```bash
ps aux | grep uvicorn
```

If not running, start it with:
```bash
python -m uvicorn daemon.server:app --host 127.0.0.1 --port 8765
```

### Issue: "Authentication failed"

**Solution:**
- Verify your PAT/password is correct
- Check your username matches your Snowflake account
- Ensure your account identifier is correct (including region)

### Issue: Query returns "Object does not exist"

**Solution:**
- Verify you have access to the database/schema/table
- Check your role has necessary permissions
- Try fully qualifying the table: `DATABASE.SCHEMA.TABLE`

### Issue: "Network timeout" or slow queries

**Solution:**
- Check your warehouse is running: `SHOW WAREHOUSES`
- Ensure warehouse is properly sized for your queries
- Try a simpler query first: `SELECT 1`

## Success Criteria

After completing all tests, you should have verified:

- ✅ Daemon starts successfully with valid credentials
- ✅ Health endpoint returns `status: "healthy"`
- ✅ Simple SELECT queries execute successfully
- ✅ Query results include data, columns, row_count, execution_time
- ✅ LIMIT clause is automatically added to SELECT queries
- ✅ SHOW/DESCRIBE commands work without LIMIT
- ✅ Write operations (INSERT, UPDATE, DELETE, etc.) are blocked
- ✅ Error messages are clear and helpful
- ✅ Connection remains active across multiple queries

## Next Steps

Once integration testing is complete, you're ready to proceed with:

- **Phase 1, Milestone 1.4**: Plugin Commands (CLI interface)
- **Phase 2**: Session Management (USE commands, state persistence)
- **Phase 3**: Connection Pool & Reliability

## Security Reminder

**Never commit your `.env` file to git!**

```bash
# Always verify before committing:
git status

# If .env appears in git status, add it to .gitignore:
echo ".env" >> .gitignore
```
