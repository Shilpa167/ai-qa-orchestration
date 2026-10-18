"""
Day 3: the run and open commands, and what run.json records.
"""

import re

from day3_lab import clinic, cli, data, decision, report, runs
from tests.day3.day3_helpers import read_run


def test_mock_single_case_run_records_the_audit_fields(mock_run):
    run = read_run(mock_run)
    item = run["items"][0]

    assert (mock_run.parent / "run.html").is_file()
    assert run["run_id"].startswith("run-")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", run["created_at"])
    assert run["git"]["commit"] == "unavailable" or re.fullmatch(r"[0-9a-f]{40}", run["git"]["commit"])
    assert run["git"]["dirty"] in (True, False, None)
    assert run["provider_mode"] == "mock" and run["label"] == "MOCK"
    assert run["model"] is None
    assert run["prompt"]["sha256"] == data.sha256_file(data.PROMPT_PATH)
    assert run["dataset"]["sha256"] == data.sha256_file(data.CASES_PATH)
    assert run["rubric"]["version"] == "day3-v1"

    assert item["case"]["approved_context"]["service_status"] == "outage"
    assert item["label"] == "MOCK"
    assert item["raw_response"] and item["parsed_response"]
    assert item["response_sha256"] == data.sha256_text(item["raw_response"])
    assert item["structural"] == {"status": "PASS", "findings": []}
    assert item["provider"]["token_usage"] is None
    assert item["provider"]["elapsed_seconds"] >= 0
    assert item["outcome"]["result"] == "REVIEW_PENDING"


def test_full_mock_run_covers_all_ten_cases_and_none_pass_unreviewed(run_cli, tmp_path):
    code, out, _ = run_cli("run", "--mode", "mock", "--out", tmp_path / "guided")

    assert code == 0
    run = read_run(tmp_path / "guided" / "run.json")
    assert len(run["items"]) == 10
    assert run["summary"]["outcomes"] == {"PASS": 0, "FAIL": 0, "ERROR": 0, "REVIEW_PENDING": 10}
    assert "MOCK run" in out


def test_html_is_labelled_mock_and_escapes_response_text(mock_run):
    page = (mock_run.parent / "run.html").read_text(encoding="utf-8")

    assert "MOCK" in page
    assert "never live model quality" in page
    assert "can&#x27;t tell you" in page  # the apostrophe in the response is escaped


def test_html_escapes_hostile_response_content(cases_document, rubric):
    # A response is untrusted text. It must appear in the page as text,
    # never as markup or script, whether or not it passes the schema.
    hostile = {
        "answer": "<script>alert('x')</script><img src=x onerror=alert(1)>",
        "service_status": "outage",
        "recovery_time": "\"><b>bold</b>",
        "next_step": "</pre><a href='javascript:alert(1)'>click</a>",
    }
    case = data.cases_by_id(cases_document)["D3-01"]
    item = runs.build_item(case, clinic.fixture_result(hostile, "MOCK"), None, item_id="x'><script>id</script>")
    item = decision.apply_review(item, [2, 2, 2, 2], "no", "<i>note</i> & stuff", "<b>reviewer</b>")
    broken = runs.build_item(case, clinic.fixture_result(hostile, "MOCK"), None)
    broken["raw_response"] = "<script>alert('raw')</script>"  # unparseable raw text
    run = runs.build_run("run", "mock", "MOCK", "note", None, [item, broken], cases_document, rubric)

    page = report.render_html(run)

    for markup in ("<script", "<img", "<b>bold", "<a href", "<i>note", "<b>reviewer", "onerror=alert(1)>"):
        assert markup not in page
    assert "&lt;script&gt;alert(" in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "&lt;/pre&gt;&lt;a href=" in page


def test_run_refuses_to_overwrite_an_earlier_run(run_cli, mock_run):
    before = mock_run.read_bytes()

    code, _, err = run_cli("run", "--mode", "mock", "--case", "D3-01", "--out", mock_run.parent)

    assert code == 2
    assert "already contains an earlier run" in err
    assert mock_run.read_bytes() == before


def test_unknown_case_is_rejected(run_cli, tmp_path):
    code, _, err = run_cli("run", "--mode", "mock", "--case", "D3-99", "--out", tmp_path / "x")

    assert code == 2
    assert "Unknown case 'D3-99'" in err
    assert not (tmp_path / "x").exists()


def test_open_uses_a_file_uri_without_launching_a_real_browser(run_cli, mock_run, monkeypatch):
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda uri: opened.append(uri) or True)

    code, out, _ = run_cli("open", mock_run.parent / "run.html")

    assert code == 0
    assert opened == [(mock_run.parent / "run.html").resolve().as_uri()]
    assert opened[0].startswith("file:")


def test_open_missing_report_fails_cleanly(run_cli, tmp_path):
    code, _, err = run_cli("open", tmp_path / "nope.html")

    assert code == 2
    assert "Report not found" in err
