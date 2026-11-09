"""GitLab URL with a group path (user decision, 2026-11-09).

The GitLab URL in the Setting tab may include the group the projects live in,
`https://gitlab.hella.com/alm/projects_group/.../e-ad_radar_cust_suz05_group`, so that a
project field only needs the short name, `SUZ05_APP_Application_Software-Impl`. The API
is always called on the host; the group is joined to a short project name.
Assumes GitLab runs at the root of its host, which holds for gitlab.hella.com.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def split_gitlab_url(url: str) -> tuple[str, str]:
    """(host URL, group path) of a GitLab URL; group is "" without a path."""
    text = (url or "").strip()
    if not text:
        return "", ""
    parts = urlsplit(text)
    host = urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")
    path = parts.path.split("/-/", 1)[0].strip("/")
    return host, path


def project_path(group: str, project: str) -> str:
    """Full project path: `group/project`, or `project` when it already has a group or there is none."""
    project = (project or "").strip().strip("/")
    if not project or "/" in project or project.isdigit() or not group:
        return project
    return f"{group}/{project}"
