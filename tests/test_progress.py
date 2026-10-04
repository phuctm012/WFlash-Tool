import pytest

from wflash.core.progress import CALCULATING_TEXT, IDLE_TEXT, ProgressEstimator, format_mmss


def test_format_mmss():
    assert format_mmss(0) == "00:00"
    assert format_mmss(75.4) == "01:15"
    assert format_mmss(3725) == "62:05"
    assert format_mmss(-3) == "00:00"


def test_idle_and_calculating_texts():
    assert IDLE_TEXT == "ETA: -- | Speed: --"
    est = ProgressEstimator(started_at=100.0)
    assert est.running_text() == CALCULATING_TEXT
    est.start(total_bytes=1024 * 1000, now=110.0)
    assert est.transferring
    est.update(0, now=111.0)
    assert est.running_text() == "ETA: calculating… | Speed: --"


def test_eta_and_speed_from_percent():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=1024 * 1000, now=10.0)  # 1000 KiB
    est.update(25, now=20.0)  # 10 s for 25 %
    assert est.eta_s == pytest.approx(30.0)
    assert est.speed_kbps == pytest.approx(25.0)  # 250 KiB / 10 s
    assert est.running_text() == "25% | ETA: 00:30 | Speed: 25.0 KB/s"


def test_none_percent_keeps_previous_values():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=2048, now=0.0)
    est.update(50, now=4.0)
    before = est.running_text()
    est.update(None, now=9.0)
    assert est.running_text() == before
    assert est.percent == 50


def test_update_before_start_is_ignored():
    est = ProgressEstimator(started_at=0.0)
    est.update(40, now=5.0)
    assert est.percent is None and est.running_text() == CALCULATING_TEXT


def test_zero_bytes_gives_eta_without_speed():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=0, now=0.0)
    est.update(50, now=2.0)
    assert est.running_text() == "50% | ETA: 00:02 | Speed: --"


def test_final_texts_use_time_since_flash_start():
    est = ProgressEstimator(started_at=100.0)
    est.start(total_bytes=1024 * 100, now=105.0)
    est.update(100, now=115.0)  # 100 KiB in 10 s
    assert est.done_text(now=172.0) == "100% | Time: 01:12 | Speed: 10.0 KB/s"
    assert est.failed_text(now=130.0) == "Failed | Time: 00:30 | Speed: --"
    assert est.cancelled_text(now=103.0) == "Cancelled | Time: 00:03"


def test_restart_clears_previous_estimate():
    est = ProgressEstimator(started_at=0.0)
    est.start(total_bytes=1024, now=0.0)
    est.update(50, now=1.0)
    est.start(total_bytes=1024, now=2.0)
    assert est.percent is None and est.eta_s is None and est.speed_kbps is None
