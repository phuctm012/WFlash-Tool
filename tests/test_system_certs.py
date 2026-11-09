"""GitLab certificates come from the system store via truststore (no CA bundle file)."""
import builtins
import logging
import sys
import types

from wflash.core import system_certs


def test_use_system_certificates_injects_truststore(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(inject_into_ssl=lambda: calls.append("inject"))
    monkeypatch.setitem(sys.modules, "truststore", fake)
    assert system_certs.use_system_certificates() is True
    assert calls == ["inject"]


def test_use_system_certificates_warns_and_carries_on_without_truststore(monkeypatch, caplog):
    real_import = builtins.__import__

    def no_truststore(name, *args, **kwargs):
        if name == "truststore":
            raise ImportError("No module named 'truststore'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "truststore", raising=False)
    monkeypatch.setattr(builtins, "__import__", no_truststore)
    with caplog.at_level(logging.WARNING, logger="wflash.certs"):
        assert system_certs.use_system_certificates() is False
    assert "pip install truststore" in caplog.text
