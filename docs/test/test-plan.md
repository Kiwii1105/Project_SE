# EduMate Test Plan

- **Owner** · Lương Duy Phước (24127509)
- **WBS** · 5.1.1
- **Version** · 0.3
- **Planned due date** · 31 October 2026 (Week 03 and Week 04)

## Scope

Test accounts, course registration, scheduling, deadline tracking and lecturer Q&A. Prioritize Must requirements FR-01–FR-09 and FR-11–FR-15, then cover Should requirements FR-10 and FR-16. F06 reminders, F07 dashboard, F08 attachments and F09 LaTeX are outside this suite.

| Milestone | Testing work |
| --- | --- |
| PA2 | Review requirements and walk through the main student and lecturer flows in the browser. |
| PA4 | Refine the plan, cases and acceptance criteria. |
| PA5 | Run the full suite, record defects, retest fixes and collect evidence. |

## Test approach

| Level | Checks | Owner |
| --- | --- | --- |
| Unit | Schedule conflicts and deadline boundaries with Python unittest | Developer |
| Integration | Flask APIs with MemoryStore, including sessions, invalid requests and enrollment updates | Tester and developer |
| System | Student and lecturer workflows in a browser against Flask and Firebase | Tester |
| Acceptance | Must scenarios against agreed acceptance criteria | Tester and Nguyễn Xuân Quyên |

Cover normal flows, invalid inputs, boundaries, permissions and state changes. Rerun affected cases after fixes and run the unit and API suite before proposing a merge.

## Non-functional checks

| Requirement | Planned check and evidence |
| --- | --- |
| NFR-01 | Run 50 concurrent users. Record P95 latency and error rate for courses, timetable, deadlines and enrollment. Target P95 ≤ 1 s per endpoint. |
| NFR-02 | At 10 Mbps with up to 50 courses, record five browser timings each for Courses, Timetable and Assignments. Target every run ≤ 2 s. |
| NFR-03 | Inspect the credential flow and record results for valid, forged, expired, wrong-audience and wrong-issuer tokens. |
| NFR-04 | Record responses from protected APIs. Expect 401 for anonymous requests and 403 for unauthorized roles or non-members where applicable. |
| NFR-05 | Record a secrets scan of tracked files and Git history. Review ignore rules. |
| NFR-06 | Observe five first-time students completing registration, enrollment and timetable access without instructions. At least four should finish within three minutes. Record anonymized times. |
| NFR-07 | Check that interface labels and error messages are in Vietnamese. |
| NFR-08 | Simulate an enrollment write failure in an isolated environment. Compare records before and after, and capture the user-facing error. |
| NFR-09 | Record results for main flows in the latest two versions of Chrome, Edge and Firefox across widths from 360 to 1920 px. |
| NFR-10 | Record line coverage for schedule overlap, conflict lookup, timetable and deadline classification algorithms. Target ≥ 80% with the suite passing. |

## Environment and test data

Install `src/requirements.txt` in `.venv`. For the [interface walkthrough](test-environment-setup.md#interface-walkthrough), use Chromium and the dedicated Firebase QA configuration in `src/.env` with Email/Password enabled. Use test-only student and lecturer accounts, a fresh registration email, a sample course with one session and an assignment due in the future. Keep the server running between role switches because MemoryStore resets on restart.

```sh
EDUMATE_STORE=memory PORT=5018 .venv/bin/python src/app.py
```

Open [EduMate on localhost](http://127.0.0.1:5018/). For full system tests, use a dedicated Firebase project with Authentication and Firestore. Keep credentials outside Git and use synthetic data. Use Asia/Ho_Chi_Minh (UTC+7) for time-based cases. Mock the clock for fixed-time checks.

Run the existing unit and API suite from the repository root. Confirm the token tests run without skips.

```sh
.venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
```

## Execution and reporting

- **Entry** · Record the build, confirm the smoke checks pass and prepare the environment, accounts and expected results.
- **Proposed exit** · Execute every Must variant, achieve at least 90% pass, resolve all Critical and High defects, and review NFR evidence. Count Blocked and Not Run variants as non-passing.
- **Results** · Record the build, environment, case variant, expected result, actual result and evidence.
- **Defects** · Record reproduction steps, severity, priority, owner and fix link. Retest before closing and reopen if the fix fails. Raise unclear requirements for clarification.
