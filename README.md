# QA Portal

A web portal that tracks the five parts of a QA portfolio project: test cases,
bug reports, Playwright automation, API testing and the README. Each part has
its own charts, a filterable table, and add, edit and delete.

## What it tracks

| Section      | Records                                                              | Charts                                                    |
| ------------ | -------------------------------------------------------------------- | --------------------------------------------------------- |
| Overview     | One headline figure per section                                      | The main chart from each section, plus results by project |
| Test-Cases/  | Functional and negative cases, priority, last result, risk covered   | Results by module; functional and negative by module      |
| Bug-Reports/ | Steps, expected, actual, severity, priority, severity rationale      | Bugs by severity; reported and resolved per week          |
| Playwright/  | Scenario, spec file, browser, last run, duration                     | Runs by browser; slowest scenarios                        |
| API-Testing/ | Method, endpoint, expected and actual status, response time          | Response time by check; results by method                 |
| README.md    | Checklist of the five README sections, per project                   | Progress meter and folder counts                          |

Every record belongs to a project. The project selector in the left rail
scopes every chart, count and table to one project, or shows all of them.

## How it runs

`qa-portfolio-tracker.html` is the source of a page published as a Claude
artifact. It is a single file: markup, styles and script, with no build step
and no libraries. The charts are drawn by the page itself.

In the artifact, records are not stored in this file. The page reads and
writes them through the artifact's shared database (`window.claude`,
capabilities `db` and `user`), in the collections `testcases`, `bugs`,
`playwright`, `api` and `readme`.

## The public site

https://www.dbqaportal.us.com is the same page served by GitHub Pages from
this branch. There is no database there, so it shows `data.json`, an export of
the artifact's records, and is read-only.

- `index.html` is built from `qa-portfolio-tracker.html` by `python build.py`.
  Edit the tracker file, then rebuild; do not edit `index.html` by hand.
- `data.json` is a snapshot. Re-export it to update what the site shows.
- `CNAME` holds the custom domain.

## Running tests from the portal

A web page cannot start programs, so `run_helper.py` does it. It serves the
portal at http://localhost:8765 and adds a "Run tests on this PC" panel to the
Playwright folder:

    python run_helper.py

- **Watch run** runs the suite in a visible browser and shows the output live.
- **Open Playwright UI** opens Playwright's own test runner for that project.

The panel appears only on that local address, never on the public site or in
the artifact. Each project's folder and commands are listed in `PROJECTS` at
the top of `run_helper.py`.

When a watch run finishes, each test's result, run date and duration are saved
to its record in `data.json`, matched by project, browser and title; a test
with no record gets a new one. A stopped run and the Playwright UI save
nothing. The artifact's database is not updated, so re-exporting `data.json`
from the artifact replaces these results.

## Projects tracked so far

- Congress Report Card: Playwright smoke suite on three browsers, plus JMeter results
- GHSA Football: Playwright smoke suite for the pages and JSON API
- Playwright framework demo: UI and API tests with response-time budgets
