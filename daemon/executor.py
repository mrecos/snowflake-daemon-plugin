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
            command = sql_upper.split()[0] if sql_upper else "UNKNOWN"
            return False, f"Only read-only queries allowed: {command}"

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
