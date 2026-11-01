# Next Chapter Monthly — Prompt 1

Generates **Your Monthly Career & Community Digest** as HTML and plain text.
The generation engine and synthetic preview remain read-only/offline respectively.
Prompt 2 adds independent demo subscriptions and guarded delivery; see
[DELIVERY.md](DELIVERY.md) for its unapplied migration, API, configuration, and limits.
Prompt 3 adds a standalone monthly command and disabled deployment examples;
see [SCHEDULING.md](SCHEDULING.md). No schedule is activated.

## Interactive dashboard view

The alumni dashboard's **View Monthly Newsletter** button opens an in-app React
view. `GET /newsletter/current` returns the current month's structured digest
for the signed synthetic demo session only. The request has no profile ID; its
subject comes from the purpose-bound bearer token. The database read verifies
`is_demo` again, uses the existing read-only newsletter generator, and sends
`Cache-Control: no-store`. It neither checks consent nor writes a delivery
ledger entry, so viewing is independent of email subscription.

Response shape: `{"month":"YYYY-MM","demo_only":true,"content":{"first_name":"Example", "jobs":[], "events":[], "cohort_message":"...", ...}}`.
The frontend renders this data as React text and safe links rather than
inserting email HTML. A real account sees an explicit unavailable state until
verified alumni authentication can establish ownership; the existing email-only
sign-in cannot do so. The current event source provides illustrative entries
without registration URLs, which are labeled as examples in the view.
The frontend requests a fresh read whenever the digest view opens; switching
demo accounts clears the prior session token and cached profile.

For a saved profile without a signed demo token, the dashboard offers a separate
synthetic-only calculation. The user must first confirm that the current profile
is fictional. Only first name, city, cohort, skills, and role titles/current flags/
dates are sent to `POST /newsletter/demo` with `synthetic: true`. It accepts no
database ID, email, salary, employer, or other extra field. This route reads
public stored jobs and aggregates of synthetic demo cohorts only; it never
retrieves an individual alumni record or writes a subscription/delivery ledger.
The existing matcher, event selection, privacy threshold, and React rendering
are reused. The confirmation lasts only for the current browser tab session and
is cleared on sign-out or account switch. Saving an updated profile causes the
view to calculate again when opened. An email-only login does not prove the
profile is fictional, so the confirmation is a user assertion, not verified
identity; production authorization for real alumni remains future work.

`POST /newsletter/demo` accepts JSON such as:

```json
{"synthetic":true,"first_name":"Jordan","city":"New York","cohort":"2022","skills":["Python"],"roles":[{"title":"Software Engineer","is_current":true,"start_date":"2025-01","end_date":""}]}
```

It returns the same `month`, `demo_only`, and `content` shape as `GET /newsletter/current`.
The request is capped at 8 KiB, allows at most 30 skills and 15 roles, and has
a best-effort 30 requests/minute per-client in-process limit. Missing optional
profile fields produce a useful empty state. The response is `no-store`.

## Safe synthetic preview (PowerShell, repository root)

The **Open Next Chapter Dashboard** button uses `NEWSLETTER_APP_URL`, defaulting
to `http://localhost:5173/`. Both preview commands and delivery share this setting;
the standalone preview's `--app-url` overrides it. Set the environment variable
in the shell generating previews. No `.env` or database configuration is loaded
by the offline preview.

Start the frontend in another PowerShell terminal from the repository root:

```powershell
Set-Location work/dashboard
npm.cmd run dev -- --port 5173 --strictPort
```

Keep Vite running while opening the HTML file. Absolute links work from a local
file; signed-out users follow the normal sign-in flow. The app uses `/` with
`?section=jobs`, `?section=events`, and `?section=profile`, not a `/dashboard` route.
Synthetic job links are explicitly illustrative. Preview unsubscribe opens
preferences; delivered emails retain their signed API unsubscribe URL.

For delivery, configure `NEWSLETTER_APP_URL` and `NEWSLETTER_PUBLIC_API_URL` with
reachable public HTTPS deployments. Local/private hosts are rejected; deployment
reachability must be verified by the operator. Localhost refers to each recipient's
own computer and is only suitable for previews. No live emails are sent by preview.

```powershell
$previewDir = Join-Path $env:TEMP ("next-chapter-newsletter-" + [guid]::NewGuid())
& .\backend\.venv\Scripts\python.exe -B -m backend.app.newsletter.preview --output-dir $previewDir --app-url http://localhost:5173
Start-Process (Join-Path $previewDir 'next-chapter-monthly.html')
Get-Content -LiteralPath (Join-Path $previewDir 'next-chapter-monthly.txt') -Encoding UTF8
```

This command imports no database configuration, requires no credentials, never
connects to Supabase, and refuses to overwrite output files. All sample jobs,
events, cohort figures, and the recipient are explicitly synthetic examples.
No personal production preview is written by the CLI.

## Internal service

```python
from backend.app.newsletter.service import generate_newsletter

newsletter = generate_newsletter(alumni_id, app_url="https://your-actual-app.example")
# newsletter.subject, newsletter.html, newsletter.text, newsletter.content
```

Use an actual deployment URL supplied by the caller; do not put secrets in it.
The service uses `work.database.database.readonly_session`: one PostgreSQL
REPEATABLE READ, database-enforced read-only snapshot. It raises `LookupError`
for an unknown profile and propagates configuration/connection errors. It does
not log or print generated content. Treat output as personal data: authorize the
caller before exposing it, and do not publish or commit real previews. This phase
deliberately adds no HTTP preview endpoint, given the existing stub alumni auth.

## Selection and privacy

- Jobs: existing `top_matches` eligibility/scoring for title family, seniority,
  city/metro/remote, and salary overlap. The same matcher now gives a small
  ranking bonus when saved `skills.name` values occur in a posting's title or
  description; skills never make an unrelated role eligible. The latest
  classifiable recorded current role takes priority, followed by historical
  titles. Up to five distinct eligible stored Greenhouse job URLs are shown;
  fewer if fewer exist. Relevant scores take priority; employer update
  timestamps break score ties, followed by existing deterministic ordering.
  Dates are labelled **employer updated**, not original posting dates. No refresh
  or invented replacement listings. Only absolute HTTP(S) application links
  without embedded credentials are included. Existing matcher has no stored
  explicit location-preference model; it uses city and remote logic.
- The greeting uses `alumni.first_name`; city and cohort use their saved alumni
  fields; career focus uses `work_experience.title`; and an optional ranking
  bonus uses `skills.name`. The newest saved salary range can also influence
  matching, but the digest never discloses it. Certifications are stored but
  the Greenhouse matcher has no certification signal, so they are not claimed
  as matching inputs.
- Events: reuse `network.events.events_for`, rank role-specific/local events,
  retain only future dates, cap at three. Current source is entirely synthetic;
  each event is marked **EXAMPLE EVENT**, explicitly not a scheduled TKH event.
  An empty source yields a community link and explanatory text.
- Cohorts: reuse analytics `_population` and `_aggregates`, retaining their
  distinct-alumnus/current-role definitions. Query only the recipient's trimmed
  cohort, separating real and demo populations. Report recorded current roles
  and confirmed resumes, never salaries or other alumni identities. Suppress
  all cohort figures for populations smaller than five. These are snapshot
  totals, with no claim about promotions or month-over-month growth. The service
  depends on these existing analytics helpers; keep their semantics compatible
  when changing analytics later.
- HTML escapes all profile, job, event, cohort, and link attribute values. Text
  carries the same picks, links, privacy notices, and empty states.
- App links select the existing React tabs via `?section=jobs`, `events`, and
  `profile`, retaining the destination through the existing sign-in flow.

## Verification

```powershell
$newsletterTestDir = Join-Path $env:TEMP ("next-chapter-tests-" + [guid]::NewGuid())
& .\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -o pythonpath=backend --basetemp $newsletterTestDir backend/tests/test_newsletter.py -q
$backendTestDir = Join-Path $env:TEMP ("next-chapter-tests-" + [guid]::NewGuid())
& .\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -o pythonpath=backend --basetemp $backendTestDir backend/tests --ignore=backend/tests/test_integration.py -q
& .\backend\.venv\Scripts\python.exe -B -c "from backend.app.main import app; from backend.app.newsletter.service import generate_newsletter; print('Imports OK')"
```

Database service tests use the existing asserted in-memory SQLite fixture in
query-only mode, with production SQLAlchemy/Psycopg connections blocked.
Do not run `test_integration.py` against Supabase: its fixture truncates tables.
Subscription/consent and mocked provider checks are documented in DELIVERY.md.
The monthly runner is documented in SCHEDULING.md. No email has been sent during implementation.
