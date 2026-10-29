# EduMate Test Environment

WBS 5.1.1 covers the test plan and environment setup. The planned due date was 31 October 2026, as recorded in Week 03 and Week 04. [Test Plan](test-plan.md) · [Week 03](../management/weekly/Week03.docx) · [Week 04](../management/weekly/Week04.docx)

## Interface walkthrough

1. From the repository root, create the Python environment and install the dependencies.

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r src/requirements.txt
   ```

2. Configure `src/.env` from the example. Use the team's Firebase QA project with Email/Password sign-in enabled. Set `FIREBASE_API_KEY` and `FIREBASE_PROJECT_ID` and keep the configuration local. [Environment example](../../src/.env.example)
3. Start the app with temporary data.

   ```sh
   EDUMATE_STORE=memory PORT=5018 .venv/bin/python src/app.py
   ```

4. Open [EduMate](http://127.0.0.1:5018/) in Chromium. Use test accounts to check registration, sign-in and sign-out. As a lecturer, create a sample course, class session and assignment. As a student, enroll and check the timetable and deadline. Keep the server running when switching roles so the sample data stays available.
