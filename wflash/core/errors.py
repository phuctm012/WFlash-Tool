"""Exception hierarchy. Every error carries a short user-facing `hint`."""
from __future__ import annotations


class WFlashError(Exception):
    default_hint = ""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint or self.default_hint


class ProfileError(WFlashError):
    default_hint = "Check the profile YAML file."


class GitLabError(WFlashError):
    default_hint = "Check the GitLab URL, token and network connection in Settings."


class ArtifactError(WFlashError):
    default_hint = "Clear the cache and download the artifact again."


class MappingError(WFlashError):
    default_hint = "Check the file mapping table and the entry names in the profile."


class WinIDEAError(WFlashError):
    default_hint = "Make sure winIDEA is running with the correct workspace."


class FlashError(WFlashError):
    default_hint = "See the log for details and try a manual download in winIDEA."


class CancelledError(WFlashError):
    default_hint = ""
