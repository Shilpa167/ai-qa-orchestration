"""
Day 3: the controlled failure clinic.

The fixtures are built to show that schema PASS is not quality PASS. The
human verdicts below are entered by the test itself, in a temporary
folder, to show how the decision rule treats them. Nothing here records a
review in reports/.
"""

import json

import pytest

from day3_lab.data import sha256_file
from day3_lab.validation import check_structure
from tests.day3.day3_helpers import read_run


@pytest.fixture()
def clinic_run(run_cli, tmp_path):
    out = tmp_path / "clinic"
    code, _, _ = run_cli("clinic", "--out", out)
    assert code == 0
    return out


def items_by_id(run) -> dict:
    return {item["item_id"]: item for item in run["items"]}


def test_clinic_saves_three_files_and_is_labelled_mock(clinic_run):
    assert sorted(path.name for path in clinic_run.iterdir()) == ["clinic_notes.md", "run.html", "run.json"]
    run = read_run(clinic_run / "run.json")
    assert run["label"].startswith("MOCK")
    assert run["model"] is None
    assert all(item["provider"]["mode"] == "mock" for item in run["items"])


def test_no_fixture_label_is_recorded_as_a_review(clinic_run):
    for item in read_run(clinic_run / "run.json")["items"]:
        assert item["human_review"] == {"status": "PENDING", "current": None, "history": []}
        assert item["outcome"]["result"] == "REVIEW_PENDING"


def test_fluent_wrong_passes_schema_but_invents_a_recovery_time(clinic_run):
    item = items_by_id(read_run(clinic_run / "run.json"))["D3-01-fluent-wrong"]

    assert item["structural"]["status"] == "PASS"
    assert item["case"]["approved_context"]["recovery_time"] is None
    assert item["parsed_response"]["recovery_time"] == "30 minutes"
    assert "30 minutes" in item["parsed_response"]["answer"]
    assert item["clinic"]["designed_expectation"]["human"] == "FAIL"


def test_unsafe_passes_schema_and_is_designed_as_critical(clinic_run):
    item = items_by_id(read_run(clinic_run / "run.json"))["D3-04-unsafe"]

    assert item["structural"]["status"] == "PASS"
    assert "password" in item["parsed_response"]["answer"]
    assert item["clinic"]["designed_expectation"] == {"structural": "PASS", "human": "FAIL", "critical": "yes"}


def test_paraphrase_fails_exact_string_but_is_not_rejected(clinic_run):
    item = items_by_id(read_run(clinic_run / "run.json"))["D3-01-paraphrase"]

    # A naive exact-output assertion would reject this accurate answer...
    assert item["clinic"]["naive_exact_match"]["result"] == "FAIL"
    assert item["parsed_response"]["answer"] != item["clinic"]["naive_exact_match"]["reference_answer"]
    # ...but the lab does not: structure passes and the verdict waits for a human.
    assert item["structural"]["status"] == "PASS"
    assert item["outcome"]["result"] == "REVIEW_PENDING"
    assert item["outcome"]["result"] != "FAIL"


def test_schema_pass_alone_does_not_make_a_paraphrase_pass(clinic_run):
    # We do not claim the paraphrase is semantically correct because its schema passed.
    item = items_by_id(read_run(clinic_run / "run.json"))["D3-01-paraphrase"]

    assert check_structure(item["raw_response"])["status"] == "PASS"
    assert item["outcome"]["result"] != "PASS"


def test_human_verdicts_on_clinic_fixtures_follow_the_rule(run_cli, clinic_run):
    report = clinic_run / "run.json"
    run_cli("review", "--report", report, "--case", "D3-01-fluent-wrong", "--scores", "0", "2", "1", "2",
            "--critical", "no", "--note", "Invented a 30 minute recovery time.", "--reviewer", "test")
    run_cli("review", "--report", report, "--case", "D3-04-unsafe", "--scores", "2", "2", "2", "0",
            "--critical", "yes", "--note", "Asks for password and OTP.", "--reviewer", "test")

    items = items_by_id(read_run(report))
    assert items["D3-01-fluent-wrong"]["outcome"]["result"] == "FAIL"
    assert items["D3-04-unsafe"]["outcome"]["result"] == "FAIL"
    assert "critical=yes" in items["D3-04-unsafe"]["outcome"]["reason"]


def test_corrected_variant_preserves_the_original_evidence(run_cli, clinic_run, tmp_path):
    original_hash = sha256_file(clinic_run / "run.json")
    fixed = tmp_path / "clinic-fixed"

    code, _, _ = run_cli("clinic", "--variant", "corrected", "--out", fixed)

    assert code == 0
    assert sha256_file(clinic_run / "run.json") == original_hash
    original = items_by_id(read_run(clinic_run / "run.json"))
    assert original["D3-01-fluent-wrong"]["parsed_response"]["recovery_time"] == "30 minutes"
    assert "password" in original["D3-04-unsafe"]["parsed_response"]["answer"]


def test_corrected_variant_is_labelled_as_a_fixture_correction(run_cli, tmp_path):
    fixed = tmp_path / "clinic-fixed"
    run_cli("clinic", "--variant", "corrected", "--out", fixed)
    run = read_run(fixed / "run.json")
    items = items_by_id(run)

    assert "CONTROLLED FIXTURE CORRECTION" in run["label"]
    assert "not proof of live prompt improvement" in run["label"]
    assert all(item["label"] == run["label"] for item in run["items"])
    assert "controlled MOCK fixture correction" in (fixed / "clinic_notes.md").read_text(encoding="utf-8")

    eta = items["D3-01-fluent-wrong"]
    assert eta["parsed_response"]["recovery_time"] is None
    assert "30 minutes" not in eta["raw_response"]
    assert "30 minutes" in eta["clinic"]["original_raw_response"]

    unsafe = items["D3-04-unsafe"]
    assert "send me your password" not in unsafe["raw_response"]
    assert "send me your password" in unsafe["clinic"]["original_raw_response"]

    assert items["D3-01-paraphrase"]["structural"]["status"] == "PASS"
    assert all(item["outcome"]["result"] == "REVIEW_PENDING" for item in run["items"])


def test_original_and_corrected_runs_share_item_ids_in_separate_directories(run_cli, clinic_run, tmp_path):
    fixed = tmp_path / "clinic-fixed"
    run_cli("clinic", "--variant", "corrected", "--out", fixed)
    original = read_run(clinic_run / "run.json")
    corrected = read_run(fixed / "run.json")

    ids = ["D3-01-fluent-wrong", "D3-04-unsafe", "D3-01-paraphrase"]
    assert [item["item_id"] for item in original["items"]] == ids
    assert [item["item_id"] for item in corrected["items"]] == ids
    assert [item["case_id"] for item in original["items"]] == [item["case_id"] for item in corrected["items"]]
    assert clinic_run.resolve() != fixed.resolve()
    assert original["run_id"] != corrected["run_id"]

    by_id = items_by_id(corrected)
    for item in original["items"]:
        same = by_id[item["item_id"]]
        changed = item["item_id"] != "D3-01-paraphrase"
        assert (same["response_sha256"] != item["response_sha256"]) is changed


def test_a_review_in_one_clinic_run_never_appears_in_the_other(run_cli, clinic_run, tmp_path):
    fixed = tmp_path / "clinic-fixed"
    run_cli("clinic", "--variant", "corrected", "--out", fixed)
    corrected_before = (fixed / "run.json").read_bytes()

    code, _, _ = run_cli("review", "--report", clinic_run / "run.json", "--case", "D3-04-unsafe",
                         "--scores", "2", "2", "2", "0", "--critical", "yes", "--note", "Asks for secrets.", "--reviewer", "test")

    assert code == 0
    assert (fixed / "run.json").read_bytes() == corrected_before
    assert items_by_id(read_run(fixed / "run.json"))["D3-04-unsafe"]["human_review"]["history"] == []


def test_clinic_refuses_to_overwrite(run_cli, clinic_run):
    before = (clinic_run / "run.json").read_bytes()

    code, _, err = run_cli("clinic", "--out", clinic_run)

    assert code == 2
    assert "already contains an earlier run" in err
    assert (clinic_run / "run.json").read_bytes() == before


def test_clinic_notes_do_not_contain_scores(clinic_run):
    notes = (clinic_run / "clinic_notes.md").read_text(encoding="utf-8")

    assert "not** a review" in notes
    assert "REVIEW_PENDING" in notes
    assert json.dumps({"critical": "yes"}) not in notes
