import os
import time
import zipfile

import pytest

from wflash.core.artifact_cache import ArtifactCache
from wflash.core.errors import ArtifactError


def make_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_miss_then_store_then_hit(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    assert cache.get(1, 10) is None
    z = make_zip(tmp_path / "a.zip", {"out/App.s3": "S0", "out/x.elf": "ELF"})
    files = cache.store_zip(1, 10, z)
    assert (files / "out" / "App.s3").read_text() == "S0"
    assert files == tmp_path / "cache" / "1" / "10" / "files"
    assert cache.get(1, 10) == files


def test_bad_zip_raises_and_leaves_no_entry(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ArtifactError):
        cache.store_zip(1, 10, bad)
    assert cache.get(1, 10) is None
    assert cache.entries() == []


def test_zip_slip_rejected(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    z = make_zip(tmp_path / "evil.zip", {"../../evil.txt": "x"})
    with pytest.raises(ArtifactError, match="Unsafe"):
        cache.store_zip(1, 10, z)
    assert not (tmp_path / "evil.txt").exists()


def test_prune_keeps_most_recent(tmp_path):
    cache = ArtifactCache(tmp_path / "cache", max_jobs=2)
    z = make_zip(tmp_path / "a.zip", {"f.s3": "x"})
    for job in (1, 2):
        cache.store_zip(5, job, z)
        marker = cache.job_dir(5, job) / ".complete"
        os.utime(marker, (time.time() - 100 + job, time.time() - 100 + job))
    cache.store_zip(5, 3, z)
    assert cache.get(5, 1) is None
    assert cache.get(5, 2) is not None
    assert cache.get(5, 3) is not None


def test_clear(tmp_path):
    cache = ArtifactCache(tmp_path / "cache")
    cache.store_zip(1, 1, make_zip(tmp_path / "a.zip", {"f": "x"}))
    cache.clear()
    assert cache.entries() == []
