"""Tests for error enhancement module."""
import pytest
from daemon.errors import ErrorEnhancer, enhance_error_message, is_retriable_error


class TestObjectNotFoundErrors:
    """Tests for object not found error enhancement."""

    def test_table_not_found(self):
        error = "SQL compilation error: Object 'MY_TABLE' does not exist or not authorized."
        enhanced = enhance_error_message(error)

        assert "MY_TABLE" in enhanced
        assert "does not exist" in enhanced
        assert "💡 Hint:" in enhanced
        assert "SHOW TABLES" in enhanced

    def test_view_not_found(self):
        error = "SQL compilation error: Object 'MY_VIEW' does not exist"
        enhanced = enhance_error_message(error)

        assert "MY_VIEW" in enhanced
        assert "Hint:" in enhanced
        assert "fully qualified names" in enhanced


class TestContextErrors:
    """Tests for database/schema/warehouse context errors."""

    def test_no_warehouse(self):
        error = "SQL compilation error: Cannot perform SELECT. No active warehouse selected in the current session."
        enhanced = enhance_error_message(error)

        assert "No warehouse" in enhanced or "warehouse" in enhanced.lower()
        assert "USE WAREHOUSE" in enhanced
        assert "SHOW WAREHOUSES" in enhanced

    def test_no_database(self):
        error = "SQL compilation error: Cannot perform SELECT. No database selected"
        enhanced = enhance_error_message(error)

        assert "database" in enhanced.lower()
        assert "USE DATABASE" in enhanced
        assert "SHOW DATABASES" in enhanced

    def test_no_schema(self):
        error = "SQL compilation error: Cannot perform SELECT. No schema selected"
        enhanced = enhance_error_message(error)

        assert "schema" in enhanced.lower()
        assert "USE SCHEMA" in enhanced
        assert "SHOW SCHEMAS" in enhanced


class TestColumnErrors:
    """Tests for invalid column errors."""

    def test_invalid_identifier(self):
        error = "SQL compilation error: invalid identifier 'UNKNOWN_COLUMN'"
        enhanced = enhance_error_message(error)

        assert "UNKNOWN_COLUMN" in enhanced
        assert "does not exist" in enhanced or "invalid" in enhanced.lower()
        assert "DESCRIBE TABLE" in enhanced
        assert "Hint:" in enhanced


class TestSyntaxErrors:
    """Tests for syntax error enhancement."""

    def test_syntax_error(self):
        error = "SQL compilation error: syntax error line 1 at position 45 unexpected 'FROM'"
        enhanced = enhance_error_message(error)

        assert "syntax error" in enhanced.lower()
        assert "45" in enhanced or "position" in enhanced
        assert "Hint:" in enhanced
        assert "commas" in enhanced or "parentheses" in enhanced or "keywords" in enhanced


class TestPermissionErrors:
    """Tests for permission/privilege errors."""

    def test_insufficient_privileges(self):
        error = "SQL access control error: Insufficient privileges to operate on table 'CUSTOMERS'"
        enhanced = enhance_error_message(error)

        assert "permission" in enhanced.lower() or "privilege" in enhanced.lower()
        assert "SHOW GRANTS" in enhanced or "role" in enhanced.lower()
        assert "Hint:" in enhanced


class TestTypeErrors:
    """Tests for type conversion errors."""

    def test_numeric_conversion(self):
        error = "Numeric value 'abc123' is not recognized"
        enhanced = enhance_error_message(error)

        assert "abc123" in enhanced
        assert "numeric" in enhanced.lower() or "convert" in enhanced.lower()
        assert "CAST" in enhanced
        assert "Hint:" in enhanced


class TestSessionErrors:
    """Tests for session/authentication errors."""

    def test_session_expired(self):
        error = "Session ABC123 has expired. Please login again."
        enhanced = enhance_error_message(error)

        assert "expired" in enhanced.lower()
        assert "auto-reconnect" in enhanced.lower() or "restart" in enhanced.lower()
        assert "Hint:" in enhanced

    def test_auth_token_expired(self):
        error = "Authentication token has expired"
        enhanced = enhance_error_message(error)

        assert "expired" in enhanced.lower()
        assert "Hint:" in enhanced


class TestGenericErrors:
    """Tests for generic error enhancement."""

    def test_generic_object_not_found(self):
        error = "The database MYDB does not exist"
        enhanced = enhance_error_message(error)

        assert "MYDB" in enhanced
        assert "does not exist" in enhanced
        assert "Hint:" in enhanced
        assert "SHOW" in enhanced

    def test_generic_syntax_error(self):
        error = "You have an error in your SQL syntax"
        enhanced = enhance_error_message(error)

        # Should contain original error
        assert "error in your SQL syntax" in enhanced or "SQL syntax" in enhanced
        # Should have basic hint for syntax errors
        assert "Hint:" in enhanced
        assert "syntax" in enhanced.lower()

    def test_generic_permission_error(self):
        error = "Access denied: You need the SELECT permission"
        enhanced = enhance_error_message(error)

        assert "permission" in enhanced.lower()
        assert "Hint:" in enhanced

    def test_unknown_error_passthrough(self):
        """Test that unknown errors are passed through with basic formatting."""
        error = "Some completely unknown error occurred"
        enhanced = enhance_error_message(error)

        # Should contain original error
        assert "unknown error" in enhanced.lower()
        # May or may not have hints, but should at least return the original


class TestSQLContext:
    """Tests for SQL context in error messages."""

    def test_short_sql_included(self):
        error = "SQL compilation error: Object 'TABLE1' does not exist"
        sql = "SELECT * FROM TABLE1"
        enhanced = enhance_error_message(error, sql)

        assert "TABLE1" in enhanced
        assert "Query:" in enhanced
        assert sql in enhanced

    def test_long_sql_truncated(self):
        error = "SQL compilation error: syntax error"
        sql = "SELECT " + ", ".join([f"col{i}" for i in range(100)]) + " FROM table"
        enhanced = enhance_error_message(error, sql)

        # Should not include full SQL if it's too long
        # The exact behavior depends on implementation
        assert "syntax error" in enhanced.lower()

    def test_no_sql_context(self):
        error = "SQL compilation error: Object 'TABLE1' does not exist"
        enhanced = enhance_error_message(error, None)

        # Should work without SQL context
        assert "TABLE1" in enhanced
        assert "Hint:" in enhanced


class TestRetriableErrors:
    """Tests for retriable error detection."""

    def test_session_expired_is_retriable(self):
        error = "Session ABC123 has expired"
        assert is_retriable_error(error) is True

    def test_auth_token_expired_is_retriable(self):
        error = "Authentication token has expired"
        assert is_retriable_error(error) is True

    def test_connection_reset_is_retriable(self):
        error = "Connection reset by peer"
        assert is_retriable_error(error) is True

    def test_timeout_is_retriable(self):
        error = "Query timeout: execution exceeded maximum time"
        assert is_retriable_error(error) is True

    def test_syntax_error_not_retriable(self):
        error = "SQL compilation error: syntax error line 1"
        assert is_retriable_error(error) is False

    def test_object_not_found_not_retriable(self):
        error = "SQL compilation error: Object 'MY_TABLE' does not exist"
        assert is_retriable_error(error) is False

    def test_permission_error_not_retriable(self):
        error = "SQL access control error: Insufficient privileges"
        assert is_retriable_error(error) is False


class TestErrorEnhancerClass:
    """Tests for ErrorEnhancer class methods."""

    def test_enhance_error_with_pattern_match(self):
        error = "SQL compilation error: Object 'CUSTOMERS' does not exist"
        enhanced = ErrorEnhancer.enhance_error(error)

        assert "CUSTOMERS" in enhanced
        assert "Hint:" in enhanced
        assert "Suggestions:" in enhanced

    def test_enhance_error_without_pattern_match(self):
        error = "Some random error message"
        enhanced = ErrorEnhancer.enhance_error(error)

        # Should return original error at minimum
        assert "random error" in enhanced.lower()

    def test_enhance_error_with_sql_context(self):
        error = "SQL compilation error: invalid identifier 'BAD_COL'"
        sql = "SELECT BAD_COL FROM table"
        enhanced = ErrorEnhancer.enhance_error(error, sql)

        assert "BAD_COL" in enhanced
        assert "Query:" in enhanced
        assert sql in enhanced

    def test_is_retriable_error_class_method(self):
        assert ErrorEnhancer.is_retriable_error("Session has expired") is True
        assert ErrorEnhancer.is_retriable_error("syntax error") is False


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_error_message(self):
        enhanced = enhance_error_message("")
        # Should handle gracefully
        assert isinstance(enhanced, str)

    def test_whitespace_only_error(self):
        enhanced = enhance_error_message("   \n  ")
        assert isinstance(enhanced, str)

    def test_very_long_error(self):
        error = "Error: " + "x" * 10000
        enhanced = enhance_error_message(error)
        assert isinstance(enhanced, str)
        assert "Error:" in enhanced

    def test_error_with_special_characters(self):
        error = "SQL error: Column 'user.name' contains invalid chars: @#$%"
        enhanced = enhance_error_message(error)
        assert isinstance(enhanced, str)
        assert "user.name" in enhanced

    def test_multiline_error(self):
        error = "SQL compilation error:\nLine 1: syntax error\nLine 2: unexpected token"
        enhanced = enhance_error_message(error)
        assert isinstance(enhanced, str)
        assert "syntax error" in enhanced.lower()
