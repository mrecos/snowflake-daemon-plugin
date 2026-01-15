from typing import Optional, Tuple
from daemon.connection import SnowflakeConnection
from daemon.models import QueryResponse
from daemon.state import StateManager
from daemon.validators import BaseValidator, ReadOnlyValidator
from daemon.errors import enhance_error_message, is_retriable_error
import time


class QueryExecutor:
    """Executes queries against Snowflake connection."""

    def __init__(
        self,
        connection: SnowflakeConnection,
        state_manager: Optional[StateManager] = None,
        validator: Optional[BaseValidator] = None
    ):
        self.connection = connection
        self.state_manager = state_manager if state_manager is not None else StateManager()
        # Default to read-only for safety, but allow override
        self.validator = validator if validator is not None else ReadOnlyValidator()

    def _validate_query(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate query using the configured validator."""
        return self.validator.validate(sql)

    def _update_state_from_use_command(self, sql: str):
        """Update state when USE command is executed."""
        sql_upper = sql.strip().upper()

        if sql_upper.startswith('USE DATABASE'):
            db_name = sql_upper.replace('USE DATABASE', '').strip().strip(';').strip('"').strip("'")
            self.state_manager.set_database(db_name)
        elif sql_upper.startswith('USE SCHEMA'):
            schema_name = sql_upper.replace('USE SCHEMA', '').strip().strip(';').strip('"').strip("'")
            self.state_manager.set_schema(schema_name)
        elif sql_upper.startswith('USE WAREHOUSE'):
            wh_name = sql_upper.replace('USE WAREHOUSE', '').strip().strip(';').strip('"').strip("'")
            self.state_manager.set_warehouse(wh_name)
        elif sql_upper.startswith('USE ROLE'):
            role_name = sql_upper.replace('USE ROLE', '').strip().strip(';').strip('"').strip("'")
            self.state_manager.set_role(role_name)

    def _is_auth_error(self, error: Exception) -> bool:
        """Check if error is an authentication/session expiry error."""
        error_str = str(error).lower()
        # Snowflake auth error codes and messages
        auth_indicators = [
            '390114',  # Authentication token has expired
            '390144',  # Session has expired
            'authentication token has expired',
            'session has expired',
            'user must authenticate again'
        ]
        return any(indicator in error_str for indicator in auth_indicators)

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

        # Try executing, with one retry on auth errors
        for attempt in range(2):
            try:
                conn = self.connection.connect()
                cursor = conn.cursor()
                cursor.execute(sql)

                # Track USE commands and update state
                if sql_upper.startswith('USE'):
                    self._update_state_from_use_command(sql)

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
                # On auth error, try to reconnect once
                if attempt == 0 and self._is_auth_error(e):
                    # Force reconnect and retry
                    self.connection.force_reconnect()
                    continue

                # Otherwise, return enhanced error
                execution_time = time.time() - start_time
                enhanced_error = enhance_error_message(str(e), sql)
                return QueryResponse(
                    success=False,
                    error=enhanced_error,
                    execution_time=execution_time
                )

        # Should never reach here, but just in case
        return QueryResponse(
            success=False,
            error="Maximum retry attempts exceeded",
            execution_time=time.time() - start_time
        )
