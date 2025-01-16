"""Nexus service network configuration."""

HOST: str = "127.0.0.1"
PORT: int = 8000

def get_url() -> str:
    """Return the URL of the Nexus service."""
    return f"http://{HOST}:{PORT}"
