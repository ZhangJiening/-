"""Regression checks for noninteractive verification lifecycle and failure reports."""
from types import SimpleNamespace
from time import perf_counter
from erlead.desktopcheck import settle
from erlead.storage import read_json


def test_settle_does_not_wait_for_a_signal_emitted_before_observer_connects(app):
    state = SimpleNamespace(busy=True)
    class LateSignal:
        def connect(self, callback):
            # Completion was already queued before the waiter subscribed.
            state.busy = False
        def disconnect(self, callback):
            pass
    state.worker = SimpleNamespace(finished=LateSignal(), isRunning=lambda: False, wait=lambda timeout: True)
    start = perf_counter()
    settle(state, app, timeout=800)
    assert perf_counter() - start < .4


def test_desktop_check_failure_is_json_and_nonzero_exit(tmp_path, monkeypatch):
    from erlead import cli, desktopcheck
    output = tmp_path / "failure.json"
    def failed(root):
        raise RuntimeError("controlled verification failure")
    monkeypatch.setattr(desktopcheck, "run_check", failed)
    monkeypatch.setattr("sys.argv", ["erlead", "desktop-test", "--workspace", str(tmp_path), "--output", str(output)])
    assert cli.main() == 1
    result = read_json(output)
    assert result["status"] == "failed" and "controlled verification failure" in result["error"]
