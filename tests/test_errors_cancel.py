import pytest

from wflash.core.cancel import CancelToken
from wflash.core.errors import (
    ArtifactError,
    CancelledError,
    FlashError,
    GitLabError,
    MappingError,
    ProfileError,
    WFlashError,
    WinIDEAError,
)


def test_error_uses_default_hint():
    err = GitLabError("boom")
    assert str(err) == "boom"
    assert err.hint == GitLabError.default_hint
    assert err.hint


def test_error_custom_hint_overrides_default():
    assert MappingError("x", hint="do this").hint == "do this"


@pytest.mark.parametrize(
    "cls",
    [ProfileError, GitLabError, ArtifactError, MappingError, WinIDEAError, FlashError, CancelledError],
)
def test_all_errors_subclass_base(cls):
    assert issubclass(cls, WFlashError)


def test_cancel_token_lifecycle():
    token = CancelToken()
    assert not token.cancelled
    token.raise_if_cancelled()
    assert token.wait(0.01) is False
    token.cancel()
    assert token.cancelled
    assert token.wait(0.01) is True
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()
