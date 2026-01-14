import httpx
import subprocess
import time
import os
from typing import Optional, Dict, Any

DAEMON_URL = "http://127.0.0.1:8765"
DAEMON_SCRIPT = "daemon.server:app"


class DaemonClient:
    """Client for communicating with the daemon."""

    def __init__(self, base_url: str = DAEMON_URL):
        self.base_url = base_url

    def is_running(self) -> bool:
        """Check if daemon is running."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=1.0)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def start_daemon(self) -> bool:
        """Start the daemon if not running."""
        if self.is_running():
            return True

        # Get the directory where this script is located
        daemon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Start daemon in background
        subprocess.Popen(
            ["python", "-m", "uvicorn", DAEMON_SCRIPT,
             "--host", "127.0.0.1", "--port", "8765"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=daemon_dir
        )

        # Wait for startup (max 5 seconds)
        for _ in range(50):
            time.sleep(0.1)
            if self.is_running():
                return True

        return False

    def health(self) -> Dict[str, Any]:
        """Get daemon health status."""
        if not self.start_daemon():
            return {
                "status": "unavailable",
                "error": "Failed to start daemon"
            }

        try:
            response = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return response.json()
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def query(self, sql: str, limit: int = 100, format: str = "table") -> Dict[str, Any]:
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
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Query timeout (exceeded 5 minutes)"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def state(self) -> Dict[str, Any]:
        """Get current session state (database, schema, warehouse, role)."""
        if not self.start_daemon():
            return {
                "error": "Failed to start daemon"
            }

        try:
            response = httpx.get(f"{self.base_url}/state", timeout=5.0)
            return response.json()
        except Exception as e:
            return {
                "error": str(e)
            }

    def stop_daemon(self) -> Dict[str, Any]:
        """Stop the daemon (graceful shutdown)."""
        if not self.is_running():
            return {"status": "not_running", "message": "Daemon is not running"}

        try:
            response = httpx.post(f"{self.base_url}/shutdown", timeout=5.0)
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
