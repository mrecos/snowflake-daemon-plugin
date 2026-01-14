# Stop Daemon - sf-stop

## Purpose
Gracefully stop the Snowflake daemon and close the connection.

## Usage
```bash
./bin/sf-stop
```

## What It Does
1. Checks if daemon is running
2. Sends shutdown signal to daemon
3. Closes Snowflake connection
4. Releases resources
5. Terminates daemon process

## Auto-Restart
The daemon will automatically restart on the next query command:
- `/snowflake-daemon:sf-query`
- `/snowflake-daemon:sf-connect`
- `/snowflake-daemon:sf-context`

## Use Cases
- **Load new code**: Stop daemon to pick up code changes
- **Close idle connection**: Free resources when not actively querying
- **Refresh session**: Force new connection on next query
- **Troubleshooting**: Reset daemon state

## Example
```bash
# Stop the daemon
./bin/sf-stop

# Output:
# Stopping Snowflake daemon...
# ✓ Daemon shutdown initiated
#
# The daemon will:
#   - Close Snowflake connection
#   - Release resources
#   - Auto-restart on next query

# Daemon auto-restarts on next query
./bin/sf-query "SELECT 1"
```

## Integration with Claude Code
Claude Code will auto-select this command when:
- User wants to stop/disconnect from Snowflake
- User wants to restart the daemon
- User mentions closing the connection
