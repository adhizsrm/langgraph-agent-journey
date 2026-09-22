import time
import subprocess
from app.execution.smoke_test import run_server_smoke_test
import sys
import threading
from unittest.mock import patch, MagicMock


# We need to simulate subprocess.Popen to emit chosen stdout lines without actually running Node.
class MockProcess:
    def __init__(self, stdout_lines):
        self.stdout_lines = stdout_lines
        self.returncode = 0
        self.pid = 12345
        self._poll = None

        # Mocks pipe reading
        class MockPipe:
            def __init__(self, lines):
                self.lines = iter(lines)

            def readline(self):
                try:
                    return next(self.lines) + "\n"
                except StopIteration:
                    return ""

            def close(self):
                pass

        self.stdout = MockPipe(stdout_lines)
        self.stderr = MockPipe([])

    def poll(self):
        return self._poll

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout):
        pass


def test_readiness_recognized_server_running_on_http_localhost_3001():
    with patch("app.execution.smoke_test.subprocess.Popen") as mock_popen, patch(
        "urllib.request.urlopen"
    ) as mock_urlopen:

        mock_proc = MockProcess(
            ["\ud83d\ude80 Server running on http://localhost:3001"]
        )
        mock_popen.return_value = mock_proc

        # We need mock_urlopen to not crash so it pretends backend works.
        mock_res = MagicMock()
        mock_res.status = 200
        mock_res.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_res

        # Provide an empty api contract so it doesn't try doing full crud
        class MockApi:
            base_route = "/api"
            operations = []

        res = run_server_smoke_test(
            ["node", "index.js"], ".", api_contract=MockApi(), timeout=0.5
        )
        assert res["startup_verified"] is True
        assert res["success"] is True


def test_readiness_recognized_server_started_on_http_localhost_3000():
    with patch("app.execution.smoke_test.subprocess.Popen") as mock_popen, patch(
        "urllib.request.urlopen"
    ) as mock_urlopen:

        mock_proc = MockProcess(["server started on http://localhost:3000"])
        mock_popen.return_value = mock_proc

        res = run_server_smoke_test(
            ["node", "index.js"], ".", api_contract=None, timeout=0.5
        )
        assert res["startup_verified"] is True
        assert res["success"] is True


def test_readiness_recognized_listening_on_port_3000():
    with patch("app.execution.smoke_test.subprocess.Popen") as mock_popen, patch(
        "urllib.request.urlopen"
    ) as mock_urlopen:

        mock_proc = MockProcess(
            ["something", "Listening on port 3000", "something else"]
        )
        mock_popen.return_value = mock_proc

        res = run_server_smoke_test(
            ["node", "index.js"], ".", api_contract=None, timeout=0.5
        )
        assert res["startup_verified"] is True
        assert res["success"] is True


def test_readiness_not_detected_unrelated_output():
    with patch("app.execution.smoke_test.subprocess.Popen") as mock_popen, patch(
        "urllib.request.urlopen"
    ) as mock_urlopen:

        mock_proc = MockProcess(["just some random logs", "compiling...", "done."])
        mock_popen.return_value = mock_proc

        res = run_server_smoke_test(
            ["node", "index.js"], ".", api_contract=None, timeout=0.5
        )
        assert res["startup_verified"] is False
        assert res["success"] is False
        assert "Timeout reached without establishing readiness" in res["error"]


def test_preserve_existing_readiness_behavior():
    with patch("app.execution.smoke_test.subprocess.Popen") as mock_popen, patch(
        "urllib.request.urlopen"
    ) as mock_urlopen:

        # Test an older style output (updated to include port to satisfy current regex)
        mock_proc = MockProcess(["app ready on port 3000 in 1500ms..."])
        mock_popen.return_value = mock_proc

        res = run_server_smoke_test(
            ["node", "index.js"], ".", api_contract=None, timeout=0.5
        )
        assert res["startup_verified"] is True
        assert res["success"] is True
