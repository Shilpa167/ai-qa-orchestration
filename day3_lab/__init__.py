"""
Day 3 response-evaluation lab for the Northstar Services IT service desk.

Run it as a module from the project root:

    python -m day3_lab validate-data
    python -m day3_lab run --mode mock --out reports/day3/guided

Modules, one job each:

    cli.py             reads the command line and calls the other modules
    data.py            loads the cases, rubric, prompt and schema; checks the dataset
    providers.py       produces a raw response (mock fixtures or the OpenAI API)
    mock_responses.py  the reviewed, fixed mock response for each of the 10 cases
    validation.py      structural checks: is it JSON, with exactly the agreed keys?
    decision.py        human review scores and the PASS/FAIL/ERROR/REVIEW_PENDING rule
    runs.py            builds, saves and reloads run.json
    report.py          renders run.json as a static run.html page
    clinic.py          the controlled failure clinic (fixed fixtures, no live calls)

Automated checks here are structural. They are NOT semantic evaluation:
whether an answer is true, relevant and safe is decided by a human.
"""
