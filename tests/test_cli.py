import subprocess
import sys


def test_cli_help_exits_zero():
    r = subprocess.run(
        [sys.executable, "-m", "traveller", "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "traveller" in r.stdout.lower() or "usage" in r.stdout.lower()
