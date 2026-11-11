"""Exception hierarchy. Every error carries a short user-facing `hint`."""
from __future__ import annotations


class WFlashError(Exception):
    default_hint = ""
    rollback_failed = False

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint or self.default_hint


class ProfileError(WFlashError):
    default_hint = "Check the profile YAML file."


class GitLabError(WFlashError):
    default_hint = "Check the GitLab URL and the access token in the Setting tab, and the network connection."


class PipelineNotReady(GitLabError):
    """The commit has no finished job yet. `waiting` is True while a job is still on its way."""

    def __init__(self, message: str, hint: str = "", waiting: bool = False) -> None:
        super().__init__(message, hint)
        self.waiting = waiting


class ArtifactError(WFlashError):
    default_hint = "Clear the cache and download the artifact again."


class MappingError(WFlashError):
    default_hint = "Check the file mapping table and the entry names in the profile."


class WinIDEAError(WFlashError):
    default_hint = "Make sure winIDEA is running with the correct workspace."


class BenchSwitchError(WFlashError):
    default_hint = "Check that Switch Debugger is running and its TCP/IP service is started."


class SourceRepoError(WFlashError):
    default_hint = "Check the source repo path, and that git is installed."


class FlashError(WFlashError):
    default_hint = "See the log for details and try a manual download in winIDEA."


class CancelledError(WFlashError):
    default_hint = ""
