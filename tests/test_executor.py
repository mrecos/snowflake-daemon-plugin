import pytest
from daemon.executor import QueryExecutor
from daemon.connection import SnowflakeConnection
from daemon.models import QueryResponse
from unittest.mock import Mock, patch


@pytest.fixture
def mock_connection():
    """Create a mock SnowflakeConnection."""
    conn = Mock(spec=SnowflakeConnection)
    return conn


@pytest.fixture
def executor(mock_connection):
    """Create a QueryExecutor with mock connection."""
    return QueryExecutor(mock_connection)


class TestQueryValidation:
    """Test query validation logic."""

    def test_validate_query_allows_select(self, executor):
        """Test that SELECT queries are allowed."""
        is_valid, error = executor._validate_query("SELECT * FROM table")
        assert is_valid is True
        assert error is None

    def test_validate_query_allows_select_lowercase(self, executor):
        """Test that lowercase SELECT queries are allowed."""
        is_valid, error = executor._validate_query("select * from table")
        assert is_valid is True
        assert error is None

    def test_validate_query_allows_with(self, executor):
        """Test that WITH (CTE) queries are allowed."""
        is_valid, error = executor._validate_query("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert is_valid is True
        assert error is None

    def test_validate_query_allows_show(self, executor):
        """Test that SHOW queries are allowed."""
        is_valid, error = executor._validate_query("SHOW TABLES")
        assert is_valid is True
        assert error is None

    def test_validate_query_allows_describe(self, executor):
        """Test that DESCRIBE queries are allowed."""
        is_valid, error = executor._validate_query("DESCRIBE TABLE my_table")
        assert is_valid is True
        assert error is None

    def test_validate_query_allows_desc(self, executor):
        """Test that DESC queries are allowed."""
        is_valid, error = executor._validate_query("DESC TABLE my_table")
        assert is_valid is True
        assert error is None

    def test_validate_query_blocks_insert(self, executor):
        """Test that INSERT queries are blocked."""
        is_valid, error = executor._validate_query("INSERT INTO table VALUES (1)")
        assert is_valid is False
        assert "read-only" in error.lower()

    def test_validate_query_blocks_update(self, executor):
        """Test that UPDATE queries are blocked."""
        is_valid, error = executor._validate_query("UPDATE table SET col=1")
        assert is_valid is False
        assert "read-only" in error.lower()

    def test_validate_query_blocks_delete(self, executor):
        """Test that DELETE queries are blocked."""
        is_valid, error = executor._validate_query("DELETE FROM table")
        assert is_valid is False
        assert "read-only" in error.lower()

    def test_validate_query_blocks_drop(self, executor):
        """Test that DROP queries are blocked."""
        is_valid, error = executor._validate_query("DROP TABLE my_table")
        assert is_valid is False
        assert "read-only" in error.lower()

    def test_validate_query_blocks_create(self, executor):
        """Test that CREATE queries are blocked."""
        is_valid, error = executor._validate_query("CREATE TABLE my_table (id INT)")
        assert is_valid is False
        assert "read-only" in error.lower()


class TestLimitAddition:
    """Test automatic LIMIT clause addition."""

    @pytest.mark.asyncio
    async def test_execute_adds_limit_to_select(self, mock_connection):
        """Test that LIMIT is added to SELECT queries without one."""
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
        assert response.success is True

    @pytest.mark.asyncio
    async def test_execute_does_not_add_limit_if_exists(self, mock_connection):
        """Test that LIMIT is not added if query already has one."""
        mock_cursor = Mock()
        mock_cursor.description = [('col1',)]
        mock_cursor.fetchall.return_value = [(1,), (2,)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SELECT * FROM table LIMIT 5", limit=10)

        # Verify original LIMIT is preserved
        call_args = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 5" in call_args
        assert "LIMIT 10" not in call_args

    @pytest.mark.asyncio
    async def test_execute_does_not_add_limit_to_show(self, mock_connection):
        """Test that LIMIT is not added to SHOW queries."""
        mock_cursor = Mock()
        mock_cursor.description = [('name',)]
        mock_cursor.fetchall.return_value = [('table1',)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SHOW TABLES", limit=10)

        # Verify LIMIT was NOT added
        call_args = mock_cursor.execute.call_args[0][0]
        assert "LIMIT" not in call_args

    @pytest.mark.asyncio
    async def test_execute_removes_trailing_semicolon_before_limit(self, mock_connection):
        """Test that trailing semicolons are removed before adding LIMIT."""
        mock_cursor = Mock()
        mock_cursor.description = [('col1',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SELECT * FROM table;", limit=10)

        # Verify semicolon removed and LIMIT added
        call_args = mock_cursor.execute.call_args[0][0]
        assert call_args.endswith("LIMIT 10")
        assert not call_args.endswith("; LIMIT 10")


class TestQueryExecution:
    """Test query execution and result handling."""

    @pytest.mark.asyncio
    async def test_execute_returns_success_response(self, mock_connection):
        """Test that successful query returns proper response."""
        mock_cursor = Mock()
        mock_cursor.description = [('id',), ('name',)]
        mock_cursor.fetchall.return_value = [(1, 'Alice'), (2, 'Bob')]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        response = await executor.execute("SELECT * FROM users", limit=10)

        assert response.success is True
        assert response.data == [(1, 'Alice'), (2, 'Bob')]
        assert response.columns == ['id', 'name']
        assert response.row_count == 2
        assert response.execution_time is not None
        assert response.execution_time > 0
        assert response.error is None

    @pytest.mark.asyncio
    async def test_execute_handles_empty_results(self, mock_connection):
        """Test that queries with no results are handled correctly."""
        mock_cursor = Mock()
        mock_cursor.description = [('id',)]
        mock_cursor.fetchall.return_value = []

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        response = await executor.execute("SELECT * FROM empty_table", limit=10)

        assert response.success is True
        assert response.data == []
        assert response.row_count == 0

    @pytest.mark.asyncio
    async def test_execute_handles_query_without_description(self, mock_connection):
        """Test that queries without description (like SHOW) are handled."""
        mock_cursor = Mock()
        mock_cursor.description = None
        mock_cursor.fetchall.return_value = []

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        response = await executor.execute("SHOW WAREHOUSES")

        assert response.success is True
        assert response.columns == []

    @pytest.mark.asyncio
    async def test_execute_closes_cursor(self, mock_connection):
        """Test that cursor is properly closed after execution."""
        mock_cursor = Mock()
        mock_cursor.description = [('id',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SELECT 1")

        mock_cursor.close.assert_called_once()


class TestErrorHandling:
    """Test error handling in query execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_error_for_invalid_query(self, executor):
        """Test that invalid queries return error response."""
        response = await executor.execute("INSERT INTO table VALUES (1)")

        assert response.success is False
        assert response.error is not None
        assert "read-only" in response.error.lower()
        assert response.data is None

    @pytest.mark.asyncio
    async def test_execute_handles_connection_error(self, mock_connection):
        """Test that connection errors are handled gracefully."""
        mock_connection.connect.side_effect = Exception("Connection failed")

        executor = QueryExecutor(mock_connection)
        response = await executor.execute("SELECT 1")

        assert response.success is False
        assert response.error == "Connection failed"
        assert response.execution_time is not None

    @pytest.mark.asyncio
    async def test_execute_handles_query_execution_error(self, mock_connection):
        """Test that query execution errors are handled gracefully."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Invalid SQL syntax")

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        response = await executor.execute("SELECT * FROM nonexistent_table")

        assert response.success is False
        assert "Invalid SQL syntax" in response.error
        assert response.execution_time is not None


class TestDefaultLimit:
    """Test default limit behavior."""

    @pytest.mark.asyncio
    async def test_execute_uses_default_limit_100(self, mock_connection):
        """Test that default limit of 100 is used when not specified."""
        mock_cursor = Mock()
        mock_cursor.description = [('id',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SELECT * FROM table")

        # Verify default LIMIT 100 was added
        call_args = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 100" in call_args

    @pytest.mark.asyncio
    async def test_execute_allows_none_limit(self, mock_connection):
        """Test that limit can be disabled by passing None."""
        mock_cursor = Mock()
        mock_cursor.description = [('id',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection.connect.return_value = mock_conn

        executor = QueryExecutor(mock_connection)
        await executor.execute("SELECT * FROM table", limit=None)

        # Verify NO LIMIT was added
        call_args = mock_cursor.execute.call_args[0][0]
        assert "LIMIT" not in call_args
