from wflash.core.gitlab_url import project_path, split_gitlab_url

GROUP = "alm/projects_group/e-ad_group/e-ad_radar_cust_suz05_group"


def test_split_with_group():
    assert split_gitlab_url(f"https://gitlab.hella.com/{GROUP}") == ("https://gitlab.hella.com", GROUP)


def test_split_trailing_slash_and_browser_tail():
    assert split_gitlab_url(f"https://gitlab.hella.com/{GROUP}/") == ("https://gitlab.hella.com", GROUP)
    assert split_gitlab_url(f"https://gitlab.hella.com/{GROUP}/-/shared") == ("https://gitlab.hella.com", GROUP)


def test_split_host_only_and_empty():
    assert split_gitlab_url("https://gitlab.hella.com") == ("https://gitlab.hella.com", "")
    assert split_gitlab_url("https://gitlab.hella.com/") == ("https://gitlab.hella.com", "")
    assert split_gitlab_url("") == ("", "")


def test_project_path_joins_short_names_only():
    assert project_path(GROUP, "SUZ05_APP") == f"{GROUP}/SUZ05_APP"
    assert project_path(GROUP, "other/group/P") == "other/group/P"  # already a full path
    assert project_path("", "SUZ05_APP") == "SUZ05_APP"
    assert project_path(GROUP, "19995") == "19995"  # a project id
    assert project_path(GROUP, "") == ""
