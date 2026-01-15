"""Enhanced error handling for Snowflake queries."""
import re
from typing import Optional, Tuple


class ErrorEnhancer:
    """Enhances Snowflake error messages with helpful hints and suggestions."""

    # Common Snowflake error patterns
    ERROR_PATTERNS = {
        # Object not found errors
        r"SQL compilation error.*Object '([^']+)' does not exist": {
            "type": "object_not_found",
            "hint": "Check if the {object_type} name is spelled correctly and exists in your current database/schema.",
            "suggestions": [
                "Run SHOW TABLES or SHOW VIEWS to see available objects",
                "Check your current context with SHOW PARAMETERS LIKE 'SEARCH_PATH'",
                "Use fully qualified names: database.schema.table"
            ]
        },

        # Schema/Database not set
        r"SQL compilation error.*Cannot perform .* No active warehouse selected": {
            "type": "no_warehouse",
            "hint": "No warehouse is selected for query execution.",
            "suggestions": [
                "Set a warehouse: USE WAREHOUSE your_warehouse",
                "Or specify in query: ALTER SESSION SET WAREHOUSE = 'your_warehouse'",
                "Check available warehouses: SHOW WAREHOUSES"
            ]
        },

        r"SQL compilation error.*Cannot perform .* No database selected": {
            "type": "no_database",
            "hint": "No database is selected. You need to specify which database to use.",
            "suggestions": [
                "Set a database: USE DATABASE your_database",
                "Use fully qualified names: database.schema.table",
                "Check available databases: SHOW DATABASES"
            ]
        },

        r"SQL compilation error.*Cannot perform .* No schema selected": {
            "type": "no_schema",
            "hint": "No schema is selected. You need to specify which schema to use.",
            "suggestions": [
                "Set a schema: USE SCHEMA your_schema",
                "Use qualified names: schema.table",
                "Check available schemas: SHOW SCHEMAS"
            ]
        },

        # Invalid column
        r"SQL compilation error.*invalid identifier '([^']+)'": {
            "type": "invalid_column",
            "hint": "Column '{match}' does not exist in the table.",
            "suggestions": [
                "Check column name spelling and capitalization",
                "Run DESCRIBE TABLE table_name to see available columns",
                "Column names are case-insensitive but must match definition"
            ]
        },

        # Syntax errors
        r"SQL compilation error.*syntax error line (\d+) at position (\d+)": {
            "type": "syntax_error",
            "hint": "SQL syntax error near position {match}.",
            "suggestions": [
                "Check for missing commas, parentheses, or keywords",
                "Verify SQL command spelling and structure",
                "Make sure quotes and brackets are balanced"
            ]
        },

        # Permission errors
        r"SQL access control error.*Insufficient privileges": {
            "type": "permission_denied",
            "hint": "You don't have permission to perform this operation.",
            "suggestions": [
                "Check your role permissions: SHOW GRANTS TO ROLE your_role",
                "Contact your Snowflake administrator for access",
                "Try switching to a role with more privileges: USE ROLE role_name"
            ]
        },

        # Type conversion errors
        r"Numeric value '([^']+)' is not recognized": {
            "type": "type_conversion",
            "hint": "Cannot convert '{match}' to a numeric type.",
            "suggestions": [
                "Check data type compatibility",
                "Use explicit type casting: CAST(column AS type)",
                "Verify input data format matches expected type"
            ]
        },

        # Duplicate key
        r"Duplicate key value violates unique constraint": {
            "type": "duplicate_key",
            "hint": "Attempting to insert a duplicate value in a unique column.",
            "suggestions": [
                "Check for existing records before inserting",
                "Use MERGE or UPDATE instead of INSERT if record might exist",
                "Verify primary key or unique constraint definitions"
            ]
        },

        # Connection/session errors
        r"(Session .* has expired|Authentication token has expired)": {
            "type": "session_expired",
            "hint": "Your session or authentication has expired.",
            "suggestions": [
                "This should auto-reconnect - if you see this, it's a bug",
                "Try running the query again",
                "Use /snowflake-daemon:sf-stop to restart the daemon"
            ]
        },

        # Invalid operation
        r"SQL execution error.*Operation not allowed": {
            "type": "invalid_operation",
            "hint": "This operation is not allowed in the current context.",
            "suggestions": [
                "Check if the operation is supported for this object type",
                "Verify you're using the correct SQL syntax for Snowflake",
                "Some operations require specific privileges or settings"
            ]
        },
    }

    @classmethod
    def enhance_error(cls, error_message: str, sql: Optional[str] = None) -> str:
        """
        Enhance a Snowflake error message with helpful hints.

        Args:
            error_message: Original error message from Snowflake
            sql: The SQL query that caused the error (optional)

        Returns:
            Enhanced error message with hints and suggestions
        """
        # Clean up the error message
        cleaned_error = error_message.strip()

        # Try to match error patterns
        for pattern, error_info in cls.ERROR_PATTERNS.items():
            match = re.search(pattern, cleaned_error, re.IGNORECASE)
            if match:
                return cls._format_enhanced_error(
                    original_error=cleaned_error,
                    error_info=error_info,
                    match_groups=match.groups() if match.groups() else None,
                    sql=sql
                )

        # No specific pattern matched, return original with basic enhancement
        return cls._format_basic_error(cleaned_error, sql)

    @classmethod
    def _format_enhanced_error(
        cls,
        original_error: str,
        error_info: dict,
        match_groups: Optional[Tuple] = None,
        sql: Optional[str] = None
    ) -> str:
        """Format an enhanced error message with hints and suggestions."""
        parts = [original_error, ""]

        # Add hint (with match group substitution if available)
        hint = error_info["hint"]
        if match_groups and "{match}" in hint:
            hint = hint.replace("{match}", match_groups[0])
        parts.append(f"💡 Hint: {hint}")

        # Add suggestions
        if error_info["suggestions"]:
            parts.append("\nSuggestions:")
            for i, suggestion in enumerate(error_info["suggestions"], 1):
                parts.append(f"  {i}. {suggestion}")

        # Add SQL context if available
        if sql and len(sql) < 200:
            parts.append(f"\nQuery: {sql[:200]}")

        return "\n".join(parts)

    @classmethod
    def _format_basic_error(cls, error_message: str, sql: Optional[str] = None) -> str:
        """Format a basic error when no specific pattern matches."""
        parts = [error_message]

        # Add generic helpful hints based on error content
        if "does not exist" in error_message.lower():
            parts.append("\n💡 Hint: The object you're referencing doesn't exist.")
            parts.append("Try running SHOW TABLES, SHOW SCHEMAS, or SHOW DATABASES to see what's available.")

        elif "syntax" in error_message.lower() and "error" in error_message.lower():
            parts.append("\n💡 Hint: There's a syntax error in your SQL query.")
            parts.append("Check for typos, missing commas, or incorrect SQL keywords.")

        elif "permission" in error_message.lower() or "privileges" in error_message.lower():
            parts.append("\n💡 Hint: You don't have permission for this operation.")
            parts.append("Contact your administrator or try a different role: USE ROLE role_name")

        # Add SQL context if available and short enough
        if sql and len(sql) < 200:
            parts.append(f"\nQuery: {sql}")

        return "\n".join(parts)

    @classmethod
    def is_retriable_error(cls, error_message: str) -> bool:
        """
        Determine if an error is retriable (transient).

        Args:
            error_message: The error message to check

        Returns:
            True if the error is retriable, False otherwise
        """
        retriable_patterns = [
            r"Session.*has expired",  # Session (with optional ID) has expired
            r"Authentication token has expired",
            r"Connection reset",
            r"Timeout",
            r"Server disconnect",
        ]

        for pattern in retriable_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True

        return False


def enhance_error_message(error: str, sql: Optional[str] = None) -> str:
    """
    Convenience function to enhance error messages.

    Args:
        error: Original error message
        sql: The SQL query that caused the error (optional)

    Returns:
        Enhanced error message with hints and suggestions
    """
    return ErrorEnhancer.enhance_error(error, sql)


def is_retriable_error(error: str) -> bool:
    """
    Convenience function to check if error is retriable.

    Args:
        error: Error message to check

    Returns:
        True if error is retriable, False otherwise
    """
    return ErrorEnhancer.is_retriable_error(error)
