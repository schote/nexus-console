"""Generate and read the authentication key of the acquisition service."""
import secrets

from console import NexusNotRunningError
from console.service.paths import authkey_path, write_atomic

AUTHKEY_NUM_BYTES = 32
"""Number of random bytes of a generated authentication key."""


def generate_authkey() -> bytes:
    """Create a fresh random authkey for this service run and persist it (0644).

    The key is written atomically, so that a client reading it concurrently
    never observes a partial key.

    Every account may use the console, so the key is readable by every account and is
    not a secret. What it does is replace the key which used to be hardcoded in this
    repository and passed on the command line: it is generated per service run, which
    keeps a client of a previous run from talking to the current service.

    Returns
    -------
        The generated authentication key.
    """
    key = secrets.token_bytes(AUTHKEY_NUM_BYTES)
    write_atomic(authkey_path(), key, mode=0o644)
    return key


def read_authkey() -> bytes:
    """Read the authkey written by the running service.

    Returns
    -------
        The authentication key of the running service.

    Raises
    ------
    NexusNotRunningError
        If the key file does not exist.
    """
    try:
        return authkey_path().read_bytes()
    except FileNotFoundError as exc:
        msg = "Nexus service is not running. Start it with: systemctl start nexus"
        raise NexusNotRunningError(msg) from exc
