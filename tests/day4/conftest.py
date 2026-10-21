"""
Day 4 fixtures and offline protection.

Fixtures in tests/day2/ and tests/day3/ are not visible here (sibling
folders), so Day 4 defines its own. Every Day 4 test:

- runs with OPENAI_API_KEY, OPENAI_MODEL and OPENAI_JUDGE_MODEL removed;
- cannot open a network connection: anything other than a loopback
  address raises, so a mistaken live call fails loudly instead of billing;
- writes reports to a temporary folder and starts every test from an EMPTY
  confirmed-reviews file, so a trainer's real reviews in
  datasets/day4/confirmed_reviews.json never change test outcomes and are
  never modified by tests.
"""

import ipaddress
import json
import shutil
import socket

import pytest

from training_day4 import cli, data


class NetworkBlocked(RuntimeError):
    pass


def _is_loopback(host) -> bool:
    if host in ("localhost", None, ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_JUDGE_MODEL"):
        monkeypatch.delenv(name, raising=False)

    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if not _is_loopback(host):
            raise NetworkBlocked(f"Day 4 tests are offline: blocked connection to {host!r}")
        return real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _is_loopback(host):
            raise NetworkBlocked(f"Day 4 tests are offline: blocked DNS lookup of {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


@pytest.fixture(autouse=True)
def isolated_outputs(monkeypatch, tmp_path):
    """Point reports and confirmed reviews at temporary files for every test.

    The confirmed-reviews file starts empty (same format as the real one),
    not as a copy: real reviews entered by a trainer must not leak in.
    """
    reports = tmp_path / "reports" / "day4"
    confirmed = tmp_path / "confirmed_reviews.json"
    real = json.loads(data.CONFIRMED_REVIEWS_PATH.read_text(encoding="utf-8"))
    confirmed.write_text(json.dumps({"format": real["format"], "notice": real["notice"], "reviews": []}), encoding="utf-8")
    monkeypatch.setattr(data, "REPORTS_DIR", reports)
    monkeypatch.setattr(data, "CONFIRMED_REVIEWS_PATH", confirmed)
    return reports


@pytest.fixture()
def cases_copy(monkeypatch, tmp_path):
    """A temporary, editable copy of cases.json that the code will read instead of the real one."""
    copy = tmp_path / "cases.json"
    shutil.copyfile(data.CASES_PATH, copy)
    monkeypatch.setattr(data, "CASES_PATH", copy)
    return copy


@pytest.fixture()
def run_cli(capsys):
    """Run the Day 4 CLI in-process. Returns (exit code, stdout, stderr)."""

    def run(*argv):
        code = cli.main([str(arg) for arg in argv])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run
