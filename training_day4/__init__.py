"""
Day 4: AI Response Evaluation, Part 2.

Run it as a module from the project root:

    python -m training_day4 --help

Modules, one job each:

    cli.py          reads the command line and calls the other modules
    data.py         paths, loading and validation of cases, labels, prompts and fixtures
    rubric.py       the four dimensions, critical categories and the PASS rule (computed in code)
    judge.py        builds the judge request and validates judge output
    clients.py      live OpenAI adapter and replay fixtures (one interface for both)
    experiments.py  judge, compare, repeat and access-check runs
    runs.py         run directories, run.json evidence and run lookup
    reviews.py      human reviews: confirmed fixed-response labels and generated-answer reviews
    calibration.py  compares a judge run with confirmed human reviews
    reporting.py    Markdown results and the summary command

Proposed labels are NOT human reviews. Judge scores are machine assessments.
Only a named trainer creates a human review, with an explicit command.
"""
