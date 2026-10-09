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

Records are not stored in this file. The page reads and writes them through
the artifact's shared database (`window.claude`, capabilities `db` and `user`),
in the collections `testcases`, `bugs`, `playwright`, `api` and `readme`.
Opened outside a Claude artifact, the page still renders but shows no records
and cannot save.

## Projects tracked so far

- Congress Report Card: Playwright smoke suite on three browsers, plus JMeter results
- GHSA Football: Playwright smoke suite for the pages and JSON API
- Playwright framework demo: UI and API tests with response-time budgets
