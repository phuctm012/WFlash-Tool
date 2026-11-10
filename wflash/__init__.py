"""WFlash: flash ECU via winIDEA from GitLab artifacts."""
__version__ = "1.0.0"  # the full version: package metadata, git tag v1.0.0, debug bundle
APP_AUTHOR = "tranph9 (TRAN Phuc)"


def display_version(version: str) -> str:
    """What the window shows: "1.0" for 1.0.0, but "1.0.1" for a patch (user decision, 2026-11-10)."""
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) == 3 and parts[2] == "0" else version


DISPLAY_VERSION = display_version(__version__)
