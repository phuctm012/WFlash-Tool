"""Shared helpers for spike scripts: tee output to a result file and connect to winIDEA."""
from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import pathlib
import platform
import sys
import traceback

OUT_DIR = pathlib.Path(__file__).parent / "results"


class Report:
    def __init__(self, name: str) -> None:
        OUT_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = OUT_DIR / f"{name}_{stamp}.txt"
        self._fh = self.path.open("w", encoding="utf-8")
        self.line(f"# {name}  {stamp}")
        self.line(f"python={sys.version}")
        self.line(f"platform={platform.platform()}")

    def line(self, text: str = "") -> None:
        print(text)
        self._fh.write(text + "\n")
        self._fh.flush()

    def section(self, title: str) -> None:
        self.line()
        self.line(f"== {title} ==")

    def exc(self, context: str) -> None:
        self.line(f"!! {context}:\n{traceback.format_exc()}")

    def close(self) -> None:
        self.line()
        self.line(f"Saved: {self.path}")
        self._fh.close()


def base_args(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--instance", help="winIDEA instance id (xem output của 01_connect.py)")
    return parser


def try_call(report: Report, label: str, fn):
    """Call fn(), log result or exception, return result or None."""
    try:
        value = fn()
    except Exception:
        report.exc(label)
        return None
    report.line(f"{label} -> {value!r}")
    return value


def connect(report: Report, instance_id: str | None):
    """Return (ic module, ConnectionMgr). Raises if connect fails."""
    import isystem.connect as ic

    report.section("isystem.connect")
    try:
        report.line(f"package version: {importlib.metadata.version('isystem.connect')}")
    except importlib.metadata.PackageNotFoundError:
        report.line("package version: unknown")
    report.line(f"module file: {getattr(ic, '__file__', '?')}")

    cmgr = ic.ConnectionMgr()

    report.section("instances")
    instances = []
    try:
        vec = ic.VectorWinIDEAInstanceInfo()
        cmgr.enumerateWinIDEAInstances("", ic.CConnectionConfig(), vec)
        for inst in vec:
            info = {
                "id": try_call(report, "  getInstanceId", inst.getInstanceId),
                "workspace": try_call(report, "  getWorkspace", inst.getWorkspace),
                "port": try_call(report, "  getTcpPort", inst.getTcpPort),
            }
            instances.append(info)
            report.line(f"instance: {info}")
    except Exception:
        report.exc("enumerateWinIDEAInstances")

    if instance_id is None and len(instances) == 1:
        instance_id = instances[0]["id"]

    report.section("connect")
    if instance_id:
        report.line(f"connecting to instance {instance_id!r}")
        try:
            cfg = ic.CConnectionConfig()
            cfg.instanceId(instance_id)
            cmgr.connect(cfg)
        except Exception:
            report.exc("connect(cfg.instanceId)")
            report.line("fallback: cmgr.connect()")
            cmgr.connect()
    else:
        report.line("no/many instances -> cmgr.connect() (most recent winIDEA)")
        cmgr.connect()
    report.line(f"isAttached: {try_call(report, 'cmgr.isAttached', cmgr.isAttached)}")
    return ic, cmgr
