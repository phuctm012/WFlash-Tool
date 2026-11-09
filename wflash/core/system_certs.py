"""HTTPS certificates from the operating system's store instead of Python's own list.

User decision (2026-11-09): no CA bundle file in WFlash. On Windows the system store holds the
company's internal certificate once IT has installed it, so GitLab works with "Verify TLS" on.
"""
from __future__ import annotations

from wflash.core.logging_setup import get_logger

log = get_logger("certs")


def use_system_certificates() -> bool:
    """Make every later HTTPS request trust the system store. Returns False when it cannot."""
    try:
        import truststore
    except ImportError:
        log.warning(
            "truststore is not installed: GitLab certificates are checked against Python's own list, "
            "which does not know an internal company certificate. Install it with: pip install truststore"
        )
        return False
    truststore.inject_into_ssl()
    log.info("HTTPS certificates are checked against the system certificate store")
    return True
