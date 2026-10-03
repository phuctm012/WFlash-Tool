import logging
import os
import sys
import time

import pytest

from wflash.core import logging_setup as ls


@pytest.fixture(autouse=True)
def _cleanup():
    ls.clear_secrets()
    yield
    ls.close_file_handler()
    ls.clear_secrets()


def test_redact_private_token_header():
    text = "headers={'PRIVATE-TOKEN': 'glpat-abc123XYZ', 'Accept': 'json'}"
    out = ls.redact(text)
    assert "glpat-abc123XYZ" not in out
    assert "PRIVATE-TOKEN': '***" in out


def test_redact_registered_secret_anywhere():
    ls.register_secret("supersecretvalue")
    assert ls.redact("url?token=supersecretvalue&x=1") == "url?token=***&x=1"


def test_register_secret_ignores_short_or_empty():
    ls.register_secret("")
    ls.register_secret(None)
    ls.register_secret("ab")
    assert ls.redact("ab cd") == "ab cd"


def test_formatter_redacts_exception_text():
    ls.register_secret("tok-999999")
    fmt = ls.RedactingFormatter(ls.LOG_FORMAT, ls.DATE_FORMAT)
    try:
        raise RuntimeError("failed with tok-999999")
    except RuntimeError:
        record = logging.LogRecord("wflash.t", logging.ERROR, __file__, 1, "oops", None, sys.exc_info())
    out = fmt.format(record)
    assert "tok-999999" not in out
    assert "RuntimeError" in out


def test_setup_logging_writes_debug_to_file(tmp_path):
    path = ls.setup_logging(tmp_path)
    ls.register_secret("hidden-token-1")
    ls.get_logger("test").debug("debug line with hidden-token-1")
    ls.close_file_handler()
    content = path.read_text(encoding="utf-8")
    assert path.parent == tmp_path
    assert path.name.startswith("wflash_") and path.suffix == ".log"
    assert "debug line with ***" in content
    assert "hidden-token-1" not in content


def test_setup_logging_keeps_latest_files(tmp_path):
    for i in range(5):
        old = tmp_path / f"wflash_2020010{i}_000000.log"
        old.write_text("x")
        os.utime(old, (time.time() - 1000 + i, time.time() - 1000 + i))
    ls.setup_logging(tmp_path, keep=3)
    remaining = sorted(p.name for p in tmp_path.glob("wflash_*.log"))
    assert len(remaining) == 3
    assert "wflash_20200104_000000.log" in remaining
    assert "wflash_20200100_000000.log" not in remaining


def test_set_verbose_toggles_calls_logger():
    ls.set_verbose(True)
    assert logging.getLogger(ls.CALLS_LOGGER).isEnabledFor(logging.DEBUG)
    ls.set_verbose(False)
    assert not logging.getLogger(ls.CALLS_LOGGER).isEnabledFor(logging.DEBUG)


def test_default_log_dir_ends_with_wflash_component():
    assert "wflash" in str(ls.default_log_dir()).lower()


def test_redact_bare_glpat_token_unregistered():
    token = "glpat-Ab3dEf6hIj9kLm2nOp5q"
    text = f"Fetched from https://example.com/api?token={token} successfully"
    out = ls.redact(text)
    assert token not in out
    assert "token=***" in out


def test_redact_bearer_token_unregistered():
    token = "glpat-Ab3dEf6hIj9kLm2nOp5q"
    text = f"Authorization: Bearer {token}"
    out = ls.redact(text)
    assert token not in out
    assert "Bearer ***" in out


def test_redact_bearer_token_case_insensitive():
    token = "glpat-Xy9zAbCdEf1gHi2jKl3m4n"
    text = f"authorization: bearer {token}"
    out = ls.redact(text)
    assert token not in out
    assert "bearer ***" in out


def test_redact_private_token_query_string_unregistered():
    token = "glpat-1a2b3c4d5e6f7g8h9i0j1k2l"
    text = f"https://gl/api?private_token={token}&x=1"
    out = ls.redact(text)
    assert token not in out
    assert "private_token=***" in out
    assert "&x=1" in out


def test_setup_logging_masks_unregistered_glpat_in_file(tmp_path):
    token = "glpat-Ab3dEf6hIj9kLm2nOp5q"
    path = ls.setup_logging(tmp_path)
    ls.get_logger("test").debug(f"Downloaded artifact with token {token}")
    ls.close_file_handler()
    content = path.read_text(encoding="utf-8")
    assert token not in content
    assert "***" in content
