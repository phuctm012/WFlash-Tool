import wflash
from wflash import display_version


def test_display_version_drops_a_zero_patch_only():
    """The window shows "v1.0" for 1.0.0 (user decision, 2026-11-10); the tag and bundle keep 1.0.0."""
    assert display_version("1.0.0") == "1.0"
    assert display_version("1.0.1") == "1.0.1"
    assert display_version("2.1.0") == "2.1"
    assert display_version("1.0") == "1.0"
    assert wflash.__version__ == "1.0.0" and wflash.DISPLAY_VERSION == "1.0"
