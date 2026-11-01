# Next Chapter

### Every Milestone Matters.

**An alumni career development and long-term impact tracking platform for The Knowledge House.**

Built by **Team 22** at **JPMorgan Chase & Co. Code for Good 2026**.

---

## Overview

Next Chapter is a full-stack web application that helps **The Knowledge House (TKH)** stay connected with alumni as they build careers in technology. Rather than relying only on occasional surveys and manual check-ins, Next Chapter gives graduates reasons to return: relevant job opportunities, a record of professional growth, community connections, and personalized monthly updates.

As alumni use the platform and update their career information, TKH gains a clearer picture of long-term outcomes and opportunities to offer support. Our goal is to make alumni engagement useful to graduates and impact measurement more sustainable for the nonprofit.

## The Challenge

Career progress continues long after graduation, but staying in touch with alumni becomes harder over time. Graduates change roles, develop skills, earn certifications, and reach important milestones that may not be captured through traditional follow-up surveys.

TKH needs a better way to understand outcomes three to five years after graduation without making alumni feel that updating their information is just another administrative task.

## Our Approach

**Create value for alumni first, then make long-term impact tracking a natural part of engagement.**

Next Chapter connects personalized career support to structured profile data. Relevant opportunities encourage alumni to return, profile updates help improve recommendations, and updated information supports TKH's understanding of graduate outcomes.

```text
Relevant career opportunities
          |
          v
    Alumni engagement
          |
          v
   Updated career profiles
          |
          v
      Cohort insights
          |
          v
  Better support from TKH
          |
          +----> Continued engagement
```

## Features

### Alumni Dashboard and Career Profiles

Alumni can maintain a central record of education, employment history, skills, certifications, and professional milestones.

Profiles provide the foundation for personalized career services while allowing TKH to better understand long-term graduate outcomes.

### Resume Parsing

The backend accepts PDF resumes and uses **Python, pdfplumber, and rule-based extraction** to identify relevant career information.

Extracted information can be reviewed and confirmed before being saved to the alumni profile in PostgreSQL.

This workflow does not require a generative AI API, OCR service, or external resume-processing service.

### Personalized Job Matches

Next Chapter integrates with the **Greenhouse public Job Board API** to retrieve available job opportunities.

A custom recommendation engine ranks opportunities using available alumni information, including:

- Current and previous job roles
- Technical skills
- Geographic location
- Relevant career experience
- Optional salary information

Relevant postings are presented with links to their original job listings.

The recommendation system also supports skill-based relevance scoring, geographic matching, and duplicate job prevention.

### Career Growth and Community

Next Chapter brings together career development and alumni engagement through profile updates, professional networking features, career resources, and community-oriented content.

The platform includes illustrative community events to demonstrate how future TKH events and networking opportunities could be surfaced to alumni.

These events are sample content, not verified scheduled events or information retrieved from a live events API.

Any production sharing of alumni contact information must incorporate appropriate consent and access controls.

### Alumni Analytics

Structured career records support administrative views of alumni outcomes, including:

- Employment and career progression
- Cohort-level trends
- Skills and professional development
- Salary records and benchmarks
- Alumni engagement and impact measurement

These insights are intended to help TKH monitor graduate outcomes and identify opportunities for continued support.

Synthetic demonstration data must not be presented as verified TKH outcomes.

### Next Chapter Monthly

**Next Chapter Monthly: Your Career & Community Digest** is a personalized newsletter designed to encourage ongoing alumni engagement.

Newsletters can incorporate:

- Personalized greetings
- Job opportunities relevant to saved roles and skills
- Geographic relevance
- Illustrative community events
- Privacy-thresholded cohort summaries
- Links back to Next Chapter

The application supports **profile-based newsletter personalization**, allowing the in-app demo experience to generate content from synthetic profile information already available in the React frontend.

This enables a demonstration of the following workflow without implementing production authentication:

```text
Resume Upload
     |
     v
Profile Review and Confirmation
     |
     v
Updated Alumni Profile
     |
     v
Personalized Job Recommendations
     |
     v
Next Chapter Monthly
```

The newsletter implementation also includes HTML and plain-text templates, subscription preferences, unsubscribe functionality, duplicate-send safeguards, delivery tracking, an optional Resend delivery adapter, and offline preview capabilities.

The standalone monthly runner is designed for **9:00 AM America/New_York on the first day of each month**.

**Automatic email scheduling and real-alumni email delivery are not currently activated.**

Production activation requires verified authentication, appropriate consent, reviewed database migrations, secure deployment configuration, and approved email delivery settings.

---

## Technology Stack

| Area | Technology |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI, Pydantic |
| API Communication | REST, JSON, Fetch API |
| Database | Supabase PostgreSQL |
| Data Access | SQLAlchemy ORM, Psycopg 3 |
| Resume Processing | pdfplumber, rule-based parsing |
| Job Opportunities | Greenhouse Job Board API |
| External HTTP Requests | httpx |
| Salary Benchmarks | Bundled BLS data snapshot |
| Newsletter Delivery | Resend API adapter (optional) |
| Testing | Python backend tests, JavaScript frontend tests |
| Collaboration | Git and GitHub |

## Architecture

Next Chapter follows a React frontend, FastAPI backend, and PostgreSQL database architecture.

```text
                 React + Vite Frontend
              Alumni and Admin Dashboards
                          |
                          |
                     REST / JSON
                      Fetch API
                          |
                          v
                   FastAPI Backend
                          |
       +------------------+-------------------+
       |                  |                   |
       v                  v                   v
 Alumni Profiles    Job Recommendations   Newsletters
       |                  |                   |
       v                  v                   v
 Resume Parsing      Greenhouse Jobs     Profile-Based
  (pdfplumber)       Matching Engine     Personalization
       |                  |                   |
       +------------------+-------------------+
                          |
                  SQLAlchemy ORM
                   + Psycopg 3
                          |
                          v
                 Supabase PostgreSQL
                    (Hosted DB)
```

### Architecture Components

**Frontend:** React and Vite provide the alumni dashboard, profile editor, resume-upload interface, job recommendations, in-app newsletter, and administrative dashboard.

**Backend:** FastAPI exposes REST endpoints for profile management, resume processing, job recommendations, newsletters, and analytics.

**Database:** Supabase PostgreSQL stores structured alumni records, employment history, skills, education, certifications, salary information, and job listings.

**Database access:** SQLAlchemy handles ORM models and database sessions. Some backend operations also use Psycopg SQL directly.

**Resume processing:** pdfplumber and deterministic parsing rules extract text and structured information from PDF resumes.

**Job recommendations:** Public Greenhouse listings are retrieved through the API, stored in PostgreSQL, and ranked against alumni information.

**Newsletters:** The newsletter generator reuses profile information, job matching, illustrative events, and privacy-thresholded cohort summaries.

**External integrations:** Greenhouse provides job listings. Resend is available as an optional, guarded email-delivery integration.

Illustrative events and pdfplumber are internal application data and libraries, respectively—not external services.

The Supabase database is hosted, but a publicly deployed frontend and backend have not been verified from the repository.

---

## Project Structure

```text
Team-22/
├── backend/
│   ├── app/                  # FastAPI application and services
│   │   ├── jobs/             # Job matching and integration
│   │   └── newsletter/       # Newsletter generation and delivery
│   ├── sql/                  # SQL migrations and supporting scripts
│   ├── tests/                # Backend tests
│   └── API_REFERENCE.md      # Backend API documentation
├── work/
│   ├── dashboard/            # React + Vite frontend
│   └── database/             # Database models and configuration
└── README.md
```

## Running Locally

These instructions use **PowerShell on Windows** and assume the repository has been cloned locally.

### 1. Clone the Repository

```powershell
git clone https://github.com/bkhackathon26/Team-22.git
cd Team-22
```

### 2. Configure the Backend

Create a Python virtual environment from the repository root:

```powershell
py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
```

Install the project's Python dependencies using the dependency manifest maintained in the repository.

Configure your local database connection in:

```text
work/database/.env
```

A SQLAlchemy-compatible PostgreSQL connection string follows this format:

```env
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/postgres
```

Use the authorized Supabase connection details for your environment.

Never commit `.env` files, credentials, signing keys, or provider tokens.

### 3. Start the FastAPI Backend

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL:

http://127.0.0.1:8000

Interactive API documentation:

http://127.0.0.1:8000/docs

### 4. Start the React Frontend

Open a separate PowerShell terminal:

```powershell
cd work\dashboard
npm install
npm run dev
```

Open the URL reported by Vite, normally:

http://localhost:5173/

Ensure the frontend API configuration points to the running FastAPI backend.

---

## API Overview

The FastAPI backend provides REST endpoints for alumni profiles, resume processing, analytics, job recommendations, and newsletter functionality.

| Endpoint | Description |
|---|---|
| `GET /health` | Backend health check |
| `GET /profiles` | List alumni profiles |
| `POST /profiles` | Create an alumni profile |
| `GET /profiles/{id}` | Retrieve a profile |
| `POST /resume/parse` | Extract information from a PDF resume |
| `POST /resume/confirm/{profile_id}` | Save reviewed resume information |
| `GET /analytics/summary` | Retrieve aggregate analytics |
| `POST /jobs/refresh` | Refresh Greenhouse job listings |
| `GET /users/{user_id}/job-matches` | Retrieve personalized job recommendations |
| `GET /newsletter/current` | Retrieve an account newsletter under existing access restrictions |

The application also provides a demo-oriented newsletter calculation pathway using synthetic profile data supplied by the frontend.

For the exact route definition and request format of the demo pathway, consult the current FastAPI `/docs` page and newsletter router.

For additional API details, see [Backend API Reference](backend/API_REFERENCE.md).

**Security note:** Some existing API endpoints are demo-oriented and require additional ownership and authorization checks before production use with real alumni data.

---

## Newsletter Preview

An offline synthetic preview allows developers to inspect a newsletter without connecting to real alumni or sending emails.

From the repository root:

```powershell
$preview = Join-Path $env:TEMP ("next-chapter-" + [guid]::NewGuid())

.\backend\.venv\Scripts\python.exe -B -m backend.app.newsletter.monthly --preview --month 2026-10 --output-dir $preview

Start-Process (Join-Path $preview "next-chapter-2026-10.html")
```

To inspect the plain-text version:

```powershell
notepad (Join-Path $preview "next-chapter-2026-10.txt")
```

For local testing, the frontend should be running if newsletter links point to `http://localhost:5173/`.

Real outgoing emails must use an authorized, publicly accessible HTTPS application URL.

After the newsletter migration has been reviewed and applied in an authorized environment, a database-backed dry run can be performed:

```powershell
.\backend\.venv\Scripts\python.exe -B -m backend.app.newsletter.monthly --dry-run --limit 10 --batch-size 5
```

For detailed configuration and delivery requirements:

- [Newsletter Delivery Documentation](backend/app/newsletter/DELIVERY.md)
- [Newsletter Scheduling Documentation](backend/app/newsletter/SCHEDULING.md)

Do not enable live delivery, schedule recurring emails, or apply migrations solely to preview a newsletter.

---

## Testing

Next Chapter includes automated tests covering backend behavior, frontend functionality, resume processing, job matching, and newsletter workflows.

During the latest reported newsletter-personalization verification, Codex confirmed:

- **325 passing backend tests**
- **25 passing frontend tests**
- Successful lint checks
- Successful frontend production build
- Synthetic profile-based newsletter personalization
- Newsletter consistency across different synthetic accounts

These results reflect the reported verification stage and should be rerun against the current repository before production deployment.

Frontend checks can be run from `work/dashboard/`:

```powershell
npm test
npm run lint
npm run build
```

Consult the repository's current test scripts and configuration for the appropriate backend test command.

**Important:** Database-mutating or destructive integration tests must be executed only in isolated, disposable test environments.

Never run destructive tests against TKH's shared Supabase database.

---

## Privacy and Deployment Considerations

Next Chapter may process personal employment histories, compensation information, contact information, and other career-related data.

Security and privacy considerations include:

- Verified authentication and account ownership
- Authorization for profile and administrative endpoints
- Appropriate consent for newsletter subscriptions
- Separate consent for networking visibility
- Protection of salary and employment information
- Privacy thresholds for cohort-level analytics
- Secure database credentials and secrets
- HTTPS for deployed application services
- Appropriate monitoring, backups, and audit practices

The current authentication implementation contains demo-oriented components and is not suitable for unrestricted real-alumni access.

The unauthenticated newsletter demonstration must remain limited to synthetic profile information and public or approved non-sensitive data.

Production deployment requires stronger authentication and authorization, reviewed schema migrations, approved infrastructure, and secure configuration.

The monthly newsletter runner is not itself an activated scheduling service.

---

## Project Handover

This section documents the application's current state and provides guidance for **The Knowledge House and future development teams** taking ownership of Next Chapter after Code for Good 2026.

### 1. Project Status at Handover

Team 22 developed Next Chapter as a functional full-stack prototype demonstrating how personalized career development services can encourage continued alumni engagement while supporting nonprofit impact measurement.

The implementation includes:

| Component | Handover Status |
|---|---|
| React alumni dashboard | Implemented |
| Alumni profile creation and editing | Implemented |
| PDF resume parsing and review | Implemented |
| PostgreSQL profile persistence | Implemented |
| Greenhouse job integration | Implemented |
| Personalized job recommendations | Implemented |
| Career and cohort analytics | Implemented |
| Administrative dashboard | Implemented |
| Interactive monthly newsletter | Implemented |
| Profile-based newsletter demo | Implemented for synthetic data |
| Production-ready authentication | Not implemented |
| Live event calendar integration | Not implemented |
| Automated newsletter delivery | Not activated |
| Public frontend/backend deployment | Not verified |

The application is intended as a foundation for continued development rather than a completed production system.

### 2. System Architecture and Development Ownership

Future maintainers should become familiar with the following directories:

| Location | Responsibility |
|---|---|
| `work/dashboard/` | React frontend, dashboard pages, and user interactions |
| `backend/app/` | FastAPI REST application and business logic |
| `backend/app/jobs/` | Greenhouse integration and recommendation logic |
| `backend/app/newsletter/` | Newsletter personalization, templates, and delivery components |
| `work/database/models.py` | SQLAlchemy database models |
| `work/database/config.py` | Database configuration and connection setup |
| `backend/sql/` | Database migration and supporting SQL |
| `backend/tests/` | Backend automated tests |
| `backend/API_REFERENCE.md` | API documentation |

The React frontend communicates with FastAPI through REST/JSON requests.

FastAPI handles data validation, profile operations, resume processing, job ranking, newsletters, and analytics.

Data is persisted in Supabase PostgreSQL through SQLAlchemy ORM and Psycopg.

The Greenhouse API supplies job listings, which are refreshed and stored locally for matching.

Newsletter generation reuses existing profile information and recommendation logic.

### 3. Local Development Handover

New developers should begin by following the **Running Locally** section of this README.

Before working on the application, confirm:

1. Python and Node.js are installed.
2. Repository access is available.
3. Required backend dependencies are installed.
4. Frontend dependencies are installed.
5. Authorized Supabase credentials have been configured.
6. Both frontend and backend can start successfully.
7. The FastAPI `/health` endpoint responds.
8. The dashboard loads and communicates with the backend.

The existing FastAPI documentation at `/docs` provides an interactive reference for inspecting API endpoints.

Developers should use synthetic data wherever possible during local testing.

### 4. Database Handover

The primary persistent datastore is **Supabase-hosted PostgreSQL**.

The core application database includes the following tables:

| Table | Purpose |
|---|---|
| `alumni` | Alumni profile information |
| `work_experience` | Employment and career history |
| `education` | Education records |
| `skills` | Technical and professional skills |
| `certifications` | Certifications and credentials |
| `resume_uploads` | Resume upload records |
| `salary_records` | Reported compensation information |
| `salary_benchmarks` | Salary reference and benchmark data |
| `jobs` | Stored job listings |

Newsletter-related tables and delivery records may require additional reviewed migrations before use.

**Database ownership and access requirements:**

- Transfer or grant appropriate Supabase project access to authorized TKH maintainers.
- Provide database configuration securely through an approved secret-management process.
- Review SQLAlchemy models and migration scripts before making schema changes.
- Establish database backup and recovery procedures.
- Apply the principle of least privilege to database credentials.
- Separate development, testing, and production environments.
- Never run destructive tests against shared data.

Maintainers should confirm the authoritative schema and migration state before introducing new features.

### 5. Resume Processing Handover

The resume-processing workflow is implemented using **pdfplumber and deterministic Python rules**.

The process follows:

```text
PDF Upload
    |
    v
Text Extraction
    |
    v
Structured Field Parsing
    |
    v
User Review
    |
    v
Profile Confirmation
    |
    v
PostgreSQL Persistence
```

This approach avoids dependency on a generative AI API.

However, resume formatting varies significantly across applicants, and rule-based extraction may not interpret every document correctly.

Maintainers should preserve the user-review step and expand parser test coverage when supporting additional resume formats.

### 6. Job Recommendation Handover

Next Chapter retrieves public job postings through the **Greenhouse Job Board API**.

Job listings can be stored in PostgreSQL and ranked against alumni profiles.

The matching implementation considers available career information such as:

- Current and historical roles
- Saved technical skills
- Geographic location
- Optional salary information

The application includes improvements for skill matching, current-role prioritization, New York metro matching, and duplicate listing prevention.

Future enhancements could include additional job providers, improved ranking algorithms, configurable career preferences, and more extensive recommendation evaluation.

Maintainers should monitor external API availability and keep stored job listings refreshed.

### 7. Newsletter Handover

**Next Chapter Monthly** is designed to provide alumni with recurring, personalized career and community updates.

The generator can use profile information such as name, role history, skills, location, and cohort.

It combines available career data with job recommendations, illustrative events, and aggregate cohort updates.

The newsletter implementation currently supports two distinct pathways:

**In-app demo personalization**

The React frontend can supply a minimized synthetic profile to the newsletter calculation flow.

This allows users to demonstrate account-based personalization without implementing production authentication.

The demonstration must not enable unrestricted access to real alumni records.

**Monthly email generation**

The backend includes newsletter templates, subscription preferences, unsubscribe functionality, delivery tracking, duplicate-send safeguards, and an optional Resend adapter.

A standalone monthly runner and example scheduling instructions are available.

However, automated email scheduling and real-alumni delivery are not activated.

Before activating production newsletters, TKH must:

- Implement verified authentication and profile ownership.
- Review and apply required newsletter database migrations.
- Confirm subscription consent requirements.
- Configure a verified sending domain.
- Configure the Resend integration securely.
- Establish a public HTTPS application URL.
- Set up an approved recurring scheduler.
- Test unsubscribe and duplicate-send behavior.
- Review privacy and data-retention practices.

For setup details, consult the newsletter delivery and scheduling documentation.

### 8. Deployment and Production Readiness

At handover, Supabase PostgreSQL is hosted, but the repository does not establish a verified public deployment of both the frontend and backend.

The React frontend may be deployed to a compatible static-hosting platform such as Vercel.

The FastAPI application requires a compatible Python hosting environment and access to the authorized PostgreSQL database.

**A secure production launch requires the following priorities:**

**Priority 1 — Authentication and Authorization**

Implement verified alumni sign-in and enforce ownership of profiles and private account information.

Review administrative access and authorization throughout the API.

**Priority 2 — Secure Hosting**

Deploy the frontend and backend, configure HTTPS, and manage environment variables securely.

Configure CORS to permit only approved frontend origins.

**Priority 3 — Database and Privacy**

Review database permissions, schema migrations, backups, consent requirements, and handling of sensitive employment and salary records.

**Priority 4 — Reliability and Monitoring**

Set up application logs, error monitoring, backups, health checks, and procedures for maintaining external integrations.

**Priority 5 — Newsletter Activation**

After authentication, infrastructure, migrations, and consent controls are verified, configure and test live email delivery and monthly scheduling.

**Priority 6 — Operational Ownership**

Assign maintainers responsible for deployments, database administration, job integration reliability, data privacy, and user support.

These steps should be completed before inviting real alumni to use the system with personal information.

### 9. Known Limitations

Future developers should be aware of the following limitations:

- **Demo-oriented authentication:** Existing sign-in mechanisms are not a replacement for production-grade identity verification and authorization.
- **Synthetic demonstration data:** Some workflows rely on simulated alumni profiles and should not be interpreted as real TKH outcomes.
- **Illustrative events:** Newsletter events are examples rather than a live integration with a verified TKH calendar.
- **Rule-based resume parsing:** Extraction accuracy depends on document formatting and should be validated by users.
- **Limited external job coverage:** Job recommendations currently rely on Greenhouse public-board listings.
- **Newsletter delivery:** Live email sending and recurring scheduling require additional configuration and authorization.
- **Deployment:** Public hosting for the complete application has not been verified.
- **Operational infrastructure:** Production monitoring, backup procedures, and access management require further review.

### 10. Handover Checklist

The following checklist is intended for TKH and any future development team.

**Repository and Documentation**

- [ ] Obtain GitHub repository access.
- [ ] Review the README and project architecture.
- [ ] Review backend API documentation.
- [ ] Identify maintainers and development responsibilities.

**Environment and Database**

- [ ] Obtain authorized Supabase project access.
- [ ] Configure database credentials securely.
- [ ] Verify database connectivity.
- [ ] Review SQLAlchemy models and database tables.
- [ ] Review pending migrations.
- [ ] Establish backup and recovery procedures.

**Application Verification**

- [ ] Start the FastAPI backend locally.
- [ ] Start the React frontend locally.
- [ ] Test synthetic alumni profile creation.
- [ ] Test resume upload, review, and confirmation.
- [ ] Verify job matching.
- [ ] Preview personalized newsletters with synthetic profiles.
- [ ] Review administrative analytics.
- [ ] Run safe backend and frontend tests.

**Production Preparation**

- [ ] Implement verified authentication.
- [ ] Enforce profile ownership and API authorization.
- [ ] Review privacy and consent requirements.
- [ ] Configure production frontend and backend hosting.
- [ ] Set up approved environment variables and HTTPS.
- [ ] Configure monitoring and operational support.
- [ ] Review newsletter email delivery and scheduling.
- [ ] Conduct a final security and deployment review.

The checklist should be completed and verified by the receiving team before production launch.

---

## Future Development

Next Chapter was developed during Code for Good as a foundation for a scalable alumni engagement platform.

Potential future enhancements include:

- Production-ready alumni authentication and authorization
- Richer longitudinal career analytics
- Additional job board integrations
- Verified TKH event calendars
- Mentorship and professional networking tools
- Expanded career development resources
- Improved job recommendation algorithms
- More extensive resume parsing capabilities
- Automated newsletter delivery
- Production deployment, monitoring, and operational support

Our long-term vision is to make Next Chapter a platform alumni continue using throughout their careers while helping The Knowledge House better understand and support the communities it serves.

## Team and Acknowledgments

Developed by **Team 22** for **The Knowledge House** during **JPMorgan Chase & Co. Code for Good 2026**.

We thank The Knowledge House and JPMorgan Chase Code for Good organizers, mentors, and volunteers for the opportunity to develop a solution focused on long-term alumni engagement and career growth.

**Next Chapter: Every Milestone Matters.**