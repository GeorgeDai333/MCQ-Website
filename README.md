# MCQ

A Django web app for teachers to build multiple-choice quizzes (ingested from
an uploaded question bank via the Claude API) and for students to take them,
with Google-authenticated logins for both roles.

## Prerequisites

- Python 3.11+
- PostgreSQL running locally (`brew install postgresql@14` on macOS, or use
  whatever Postgres you already have)
- A Google OAuth Client ID/Secret (Google Cloud Console -> APIs & Services ->
  Credentials -> Create OAuth client ID -> Web application). Add these
  Authorized redirect URIs:
  - `http://localhost:8000/accounts/google/login/callback/`
  - `http://127.0.0.1:8000/accounts/google/login/callback/`
- An Anthropic API key (for parsing uploaded question banks)

## Setup

```bash
# from the mcqsite/ directory (this file's directory)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

createdb mcq_dev   # or: psql -c "CREATE DATABASE mcq_dev;"

cp .env.example .env
# edit .env: DATABASE_URL, DJANGO_SECRET_KEY, GOOGLE_CLIENT_ID/SECRET, ANTHROPIC_API_KEY

python manage.py migrate
python manage.py createsuperuser
python manage.py setup_google_app   # provisions the allauth Google SocialApp from env vars
python manage.py runserver
```

Then:
1. Visit `/admin/`, log in with the superuser account, and add your teacher
   email(s) at **Accounts -> Teacher allowlist entries**. Only allowlisted
   emails become teachers on first Google login; everyone else becomes a
   student automatically.
2. Visit `/` and use the Student or Teacher login button (both go through
   Google).

### Local admin login

A Django superuser already exists on this machine's local dev database for
logging into `/admin/` to manage the teacher allowlist:

- URL: `http://localhost:8000/admin/`
- Username: `admin`
- Password: `XJXbcghA1uuiDW1VP9LZ`

This is a local-dev credential only (not tied to Google login). Change it
with `python manage.py changepassword admin`, and don't commit this file to
a public repo without scrubbing it first.

## Manual testing (no automated test suite by design)

Set `MCQ_INGESTION_FAKE=True` in `.env` to skip real Claude API calls while
testing the upload flow. The fake parser expects a file shaped like:

```
1. What is 2 + 2?
A) 3
B) 4
C) 5
D) 6

2. What is the capital of France?
A) London
B) Paris
C) Berlin
D) Madrid

Answer Key
1. B
2. B
```

Suggested end-to-end walkthrough:

1. **Teacher creates a quiz**: log in as an allowlisted teacher -> New Quiz
   -> fill metadata (try a short `duration_minutes` like 1-2 for testing
   expiry) -> upload the sample file above -> review/edit the parsed
   questions -> Confirm & Activate.
2. **Non-allowlisted login**: log in with a different Google account not on
   the allowlist -> confirm it lands as a student and teacher URLs 403.
3. **Student takes and passes**: as a student, once `opening_time` has
   passed, take the quiz, answer correctly, submit, verify "Passed" and the
   score on both the results page and dashboard.
4. **Student fails + retake**: fail on purpose; if retakes are allowed,
   verify the retake button appears and produces a different random
   question sample; if not allowed, verify no retake button.
5. **Autosave recovery**: start an attempt, answer a few questions, close
   the tab, reopen the same attempt URL -> verify previously-saved answers
   are pre-filled.
6. **Auto-submit on expiry**: start an attempt on a quiz with a very short
   duration, leave it idle past the deadline, then revisit the dashboard or
   attempt page -> verify it auto-submitted and graded.
7. **Auto-submit on closing time**: set a near-term `closing_time` with a
   long duration -> verify closing time (not duration) triggers submission.
8. **Edit-lock enforcement**: verify Edit works before `opening_time` and
   before any attempt exists, and is blocked (with an explanation) once
   either condition trips.
9. **CSV export**: after a few attempts, download the CSV from the teacher
   dashboard and check it matches.
10. **Docx export**: download the printable sample docx and open it.
11. **Class average toggle**: verify the average is hidden when the option
    is off, and shown/correct on both the dashboard and quiz page once on.
12. **Ownership check**: as a second student, try to open another student's
    attempt URL directly -> verify 403/404.

Optionally run `python manage.py expire_stale_attempts` to force an
immediate sweep of any expired-but-unrevisited attempts (this also runs
automatically whenever a CSV/average is computed).

## Project layout

- `accounts/` -- user roles (`Profile`), teacher allowlist, Google-login
  entry points.
- `quizzes/` -- the quiz domain: models, teacher/student views, sampling,
  grading, CSV/docx export, the `expire_stale_attempts` command.
- `ingestion/` -- the Claude API boundary: file text extraction, prompt/tool
  schema, pydantic validation.
