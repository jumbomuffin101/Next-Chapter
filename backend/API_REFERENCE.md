# TKH frontend API handoff

Base URL: `http://127.0.0.1:8000`. Interactive contracts: `/docs`; OpenAPI: `/openapi.json`.
All IDs are UUID strings. Dates use ISO strings, timestamps include their timezone,
and unavailable fields use JSON `null`. Examples below are illustrative synthetic data.
The React application is unchanged. Existing development CORS permits frontend requests.

## Run from the repository root (PowerShell)

```powershell
Set-Location 'C:\Users\Aryan Rawat\Downloads\Projects\Team-22'
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
& .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep the existing `work/database/.env`. External `DATABASE_URL` takes precedence.
Never provide database credentials to React. If rebuilding the environment, create
`backend/.venv` first with a working Python 3.12 installation.

## Endpoint index

| Method | URL | Purpose |
|---|---|---|
| GET | `/health` | Liveness: `{"ok":true}`; does not probe PostgreSQL. |
| GET | `/profiles` | Paginated alumni and selected current role. |
| POST | `/profiles` | Create/return an alumni identity; existing stub login. Writes data. |
| GET | `/profiles/{profile_id}` | Alumni details and career history. |
| GET | `/profiles/outreach` | Confirmed-resume freshness indicators. |
| GET | `/analytics/summary` | Distinct-alumni analytics and demo/real splits. |
| POST | `/resume/parse` | Parse PDF for review; no persistence. |
| POST | `/resume/confirm/{profile_id}` | Persist reviewed data atomically. Writes data. |
| GET | `/users/{user_id}/job-matches` | Rank existing stored Greenhouse listings. |
| POST | `/jobs/refresh` | On-demand Greenhouse ingestion. Writes/deletes listing rows. Admin token required (401 without it). |
| GET | `/profiles/{profile_id}/invite` | The alum's invite code (made on first request) and how many joined through it. Writes data once. |
| GET | `/invites/{code}` | Inviter's first name and cohort for the sign-up page; 404 if unknown. |
| GET | `/admin/automation` | Admin: peer-email switch, outbox counts and newest emails, sign-ups via invite/QR, newsletter status (monthly switch, mode, opted-in count, this month's deliveries, next send). |
| POST | `/admin/automation/emails` | Admin: `{"enabled": true|false}` turns the automated emails on or off. Writes data. |
| POST | `/admin/automation/newsletter` | Admin: `{"enabled": true|false}` turns the scheduled monthly newsletter on or off (on by default). Writes data. |
| POST | `/admin/automation/newsletter/send` | Admin: `{"email": "..."}` sends this month's newsletter to one demo alum who opted in (a dry-run ledger row unless live). Writes data. |

No request bodies are required for GET endpoints or `/jobs/refresh`.
The identity endpoint is still a stub, not authentication/authorization. Use this
backend for a controlled hackathon demo; access control remains future work.

## Alumni list and detail

`GET /profiles?limit=20&offset=0&cohort=2022&city=New%20York`

`limit`: 1–100, default 20. `offset`: >=0, default 0. Optional city/cohort filters
are exact, case-insensitive matches with surrounding input whitespace removed.
Ordering is surname, first name (case-insensitive), then UUID. `total` counts all
matching alumni, including when the page is empty.

```json
{
  "items": [{
    "id": "11111111-1111-4111-8111-111111111111",
    "full_name": "Example Person", "email": "example@example.com",
    "city": "New York", "cohort": "2022", "graduation_year": 2022,
    "is_demo": true, "last_updated_at": "2026-10-16T12:00:00Z",
    "current_role": {"title": "Engineer", "employer": "Demo Company", "start_date": "2024-01-01"}
  }],
  "total": 1, "limit": 20, "offset": 0
}
```

The selected role is marked current, has no end date, and does not start in the
future. Most recent known start wins, then UUID; no eligible role yields `null`.
An empty result is `{"items":[],"total":0,"limit":20,"offset":0}`.

`POST /profiles` accepts:

```json
{"email":"example@example.com","full_name":"Example Person","city":"New York"}
```

Only email is required. Returns `id`, `email`, `full_name`, and `city`.

`GET /profiles/{profile_id}` returns existing keys: `id`, `email`, `full_name`,
`phone`, `city`, `cohort`, `graduation_year`, `is_demo`, `created_at`,
`last_updated_at`, `salary_min`, `salary_max`, `salary_source`,
`work_experiences`, `education`, `skills`, `certifications`.
Work rows contain `id`, `alumni_id`, `employer`, `title`, `location`, `start_date`,
`end_date`, `is_current`, `description`, and `source`. Education rows contain
`id`, `alumni_id`, `school`, `degree`, `field_of_study`, and `graduation_year`.
Skills/certifications are arrays of strings. Note plural `work_experiences` in
profile detail versus singular `work_experience` in resume payloads.

## Dashboard analytics

`GET /analytics/summary?include_demo=true`

```json
{
  "total_alumni": 2,
  "alumni_with_current_roles": 1,
  "alumni_with_confirmed_resumes": 1,
  "total_career_history_records": 3,
  "demo": {"total_alumni":1,"alumni_with_current_roles":1,"alumni_with_confirmed_resumes":1,"total_career_history_records":2},
  "real": {"total_alumni":1,"alumni_with_current_roles":0,"alumni_with_confirmed_resumes":0,"total_career_history_records":1},
  "by_cohort": [{
    "cohort":"2022", "total_alumni":2,"alumni_with_current_roles":1,"alumni_with_confirmed_resumes":1,"total_career_history_records":3,
    "demo":{"total_alumni":1,"alumni_with_current_roles":1,"alumni_with_confirmed_resumes":1,"total_career_history_records":2},
    "real":{"total_alumni":1,"alumni_with_current_roles":0,"alumni_with_confirmed_resumes":0,"total_career_history_records":1}
  }],
  "by_city": [{
    "city":null, "total_alumni":2,"alumni_with_current_roles":1,"alumni_with_confirmed_resumes":1,"total_career_history_records":3,
    "demo":{"total_alumni":1,"alumni_with_current_roles":1,"alumni_with_confirmed_resumes":1,"total_career_history_records":2},
    "real":{"total_alumni":1,"alumni_with_current_roles":0,"alumni_with_confirmed_resumes":0,"total_career_history_records":1}
  }],
  "data_note":"Demo records are synthetic. Recorded current roles and confirmed resumes do not establish verified employment outcomes."
}
```

Current-role eligibility matches the alumni list. Multiple roles/uploads count an
alumnus once in the corresponding metric. Career-history records count all roles.
Missing/blank cohort/city values group under `null`; display as "Unknown".
Every group has the same four metrics and demo/real segments. `real` means
`is_demo=false`, not externally verified employment. Use `include_demo=false`
to exclude synthetic records from all totals and breakdowns. Empty populations
produce zero metrics and empty breakdown arrays.

## Resume upload, review, and confirmation

1. `POST /resume/parse` with multipart field **file** (text-based PDF, <=5 MiB).
2. Display returned fields and `warnings`; allow editing. Parsing does not save data.
3. After explicit review, send `POST /resume/confirm/{profile_id}`:

```json
{
  "resume": {
    "full_name":"Example Person", "email":"example@example.com", "phone":null,
    "location":"New York", "education":[],
    "work_experience":[{
      "employer":"Demo Company", "title":"Engineer", "location":"New York",
      "start_date":"2024-01", "end_date":null, "is_current":true, "description":null
    }],
    "skills":["Python","SQL"], "certifications":[], "warnings":[]
  },
  "salary_min":70000, "salary_max":90000, "file_name":"reviewed_resume.pdf"
}
```

The parser returns the inner `resume` shape. It is rule-based, without an LLM or
OCR. Name/email may initially be missing; fix them before confirmation.
Education items use `school`, optional `degree`, `field_of_study`, `start_date`,
and `end_date`. The database stores education graduation year only.

Confirmation requires a nonblank name and valid email. Every submitted role
requires employer/title; every education item requires school. Empty experience
arrays are allowed. Dates accept `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`; partial dates
use January/the first day for storage, and full dates retain their day. Original
reviewed values are retained in the snapshot. Reversed dates, ended/future roles
marked current, conflicting emails, and oversized database fields return 422.
Omitted historical roles are preserved. Job identity is case-insensitive
employer/title plus normalized start date; repeated confirmations update it.

Salary bounds are optional together, nonnegative whole annual amounts, minimum
<= maximum, each <=9,999,999,999. Omission preserves existing salary records.
Same-day self-reported salary is updated; other days remain history. Salary
currency is not stored, so agree a consistent currency/basis for the demo.
Filename defaults to `uploaded_resume.pdf`; no PDF bytes are stored.

Response contract is preserved:

```json
{"profile_id":"11111111-1111-4111-8111-111111111111","roles_added":1,"roles_updated":0,"salary_saved":true}
```

One transaction saves identity, careers, education, skills, certifications,
salary, confirmed snapshot, and freshness timestamp. Failure rolls everything
back. Reconfirming creates a new snapshot but does not duplicate job identities.

## Outreach indicators

`GET /profiles/outreach?limit=20&offset=0&stale_days=180&only_needs_outreach=true&include_demo=true`

```json
{
  "items":[{
    "id":"11111111-1111-4111-8111-111111111111", "full_name":"Example Person",
    "email":"example@example.com", "city":"New York", "cohort":"2022", "is_demo":true,
    "last_confirmed_at":null, "needs_outreach":true,
    "outreach_reason":"No confirmed resume update"
  }],
  "total":1, "limit":20, "offset":0, "stale_days":180,
  "as_of":"2026-10-16T12:00:00Z"
}
```

Freshness uses the latest **confirmed snapshot timestamp**, not generic profile
edits or unconfirmed uploads. Stale means strictly older than `stale_days`
(default 180 fixed days, allowed 1–3650). The other reason is
"No confirmed resume update in the last 180 days". `only_needs_outreach=false`
also returns fresh profiles, with `needs_outreach=false` and reason `null`.
Pagination bounds match `/profiles`. No messages are sent.

## Stored job matches

`GET /users/{user_id}/job-matches?limit=10` (positive limit; capped at 20):

```json
{"matches":[{
  "job_id":"22222222-2222-4222-8222-222222222222", "title":"Software Engineer",
  "company":"Demo Company", "location":"New York, NY", "salary_min":null,"salary_max":null,
  "apply_url":"https://example.com/jobs/1", "score":4.5, "why_matched":"Similar role, Same metro area"
}]}
```

Uses existing stored listings, career-title relevance, seniority, location, and
optional salary overlap. Empty matches are valid. Skills/embeddings are not used.
`POST /jobs/refresh` is an explicit data-writing operation, never automatic:
`{"boards":13,"jobs_upserted":0,"per_board":{},"failed":{}}`.
Failed boards retain their listings; successful empty boards clear stale ones.
No live refresh was run during backend verification.

## Errors and safe verification

400: wrong upload type. 404: missing profile, or no usable matching title.
413: oversized PDF. 422: invalid request/confirmation/PDF. Error body uses FastAPI
`detail` (string for domain errors, validation array for field errors).
An empty resume now returns 422; a valid confirmation for an unknown UUID returns 404.

```powershell
# Offline suite: excludes the legacy destructive integration fixture.
& .\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -o pythonpath=backend backend/tests --ignore=backend/tests/test_integration.py -q

# Live GET/SELECT/SHOW checks; database-enforced read-only transactions.
& .\backend\.venv\Scripts\python.exe -B -m backend.scripts.check_readonly
```

Write tests create only an asserted in-memory SQLite database and block both live
database clients. PostgreSQL-specific locking/concurrent writes are not exercised
against Supabase. Never run the legacy integration file, seed scripts, migrations,
schema initialization, refresh, or confirmation as part of live verification.
