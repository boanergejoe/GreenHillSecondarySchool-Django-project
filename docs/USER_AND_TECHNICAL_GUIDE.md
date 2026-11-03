# Green Hill Website: User and Technical Guide

## 1. User guide

### Sign in

Open the school website and choose **Portal Login**. Sign in with the username and password provided by the school administrator. Use **Change Password** after the first sign-in and do not share an account.

### Administrator

Administrators manage school setup and staff accounts. To create a Registrar account:

1. Sign in as an administrator.
2. Open **Staff Accounts** and choose **Add Staff Account**.
3. Enter the staff member's name, username, and a temporary password of at least eight characters.
4. Choose **Registrar** as the role and save.
5. Give the staff member their login details privately; ask them to change their password after signing in.

Create a separate account for each staff member. Do not assign an administrator role unless the person needs full system administration.

The local demo database includes `registrar` / `Registrar@12345`, created by `python manage.py seed_demo`. This is a public, predictable demo password; use it only in a local test database. Do not use it on PythonAnywhere. On the hosted site, the administrator must create a separate Registrar account using the steps above and set a unique password.

### Registrar

The Registrar dashboard is available at **Dashboard** after signing in. It provides active and archived student totals, recent student registrations, and links to student registration, all student records, and archived records. The sidebar provides access to student records, archived students, parents/guardians, and enrollments.

Registrars can register and update students, manage enrollments, archive and restore records, approve student-submitted re-admission requests, and directly re-admit returning students from student records. Student requests do not change enrollment until approved. The dashboard and **Re-admission Requests** page show pending requests; approve to apply the selected current-year class and terms, or decline with an optional note. Archiving retains the record and history; it is not permanent deletion. Registrar access to medical fields is restricted in student detail views.

### Teachers

Use **My Subjects** to see assigned subjects and classes. Use **Examinations** to enter marks for assigned subjects and students in eligible classes. Assignments and quizzes are managed from their respective sidebar links. AI-generated quizzes are drafts: check the questions and answer keys before publishing. AI-written-answer scores are suggestions only and require teacher review and saving.

### Finance staff

Use **Fee Structure** to maintain charges and **Payments** to record receipts. Confirm the student and fee before saving. Payment totals, balances, receipts, and the dashboard collection trend are available in finance pages.

### Students and parents

Students can review published results, attendance, assigned subjects, assignments, report cards, and fee-based exam eligibility. The student dashboard's **Request Re-admission** action submits a class/term request to the Registrar; it does not change the official enrollment until approved. Parents can review information for linked children. Eligibility is informational and does not replace the school's final examination decision.

### Public website

The public homepage contains school information, term dates, current subjects, approved announcements, contact information, and an information assistant. The assistant can answer only using approved public information. Do not enter student names, health data, passwords, or payment details.

## 2. Technical guide

### Local development

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

The seeded accounts and passwords in the repository README are for local testing only. Never use them for a public production site.

### AI configuration

The application calls OpenAI's Chat Completions API using the server-side `OPENAI_API_KEY` environment variable. The project ID and API-key tracking/identifier values are not credentials and cannot authenticate requests. Create an actual secret API key in the OpenAI platform, ensure its project has API access/billing and permission for the configured model, and store that secret privately. Do not paste it into source code, templates, Git, screenshots, or chat.

Set the key for a local PowerShell session, then start the server in that same session:

```powershell
$env:OPENAI_API_KEY = "set-the-secret-key-here"
$env:OPENAI_MODEL = "gpt-4o-mini"
python manage.py runserver
```

To confirm provider connectivity, run:

```powershell
python manage.py check_ai
```

The command sends a short, non-student test prompt and prints only success or a provider/configuration error. It makes a real API request and may incur a small provider charge. The site also uses AI for question generation, teacher-reviewed written-answer suggestions, and public school questions. These features require the same configured key and an outbound network connection from the host.

Written-answer suggestions send the assignment prompt and submitted answer to the configured AI provider. Follow the school's privacy policy and avoid including student names or other identifying details in submitted content unless the school has approved that processing.

### PythonAnywhere deployment

1. Pull the application changes into the configured source directory and activate the web app's virtual environment.
2. Install requirements if needed, then run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
3. Configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` for the live domain.
4. Add `OPENAI_API_KEY` as a private environment variable available to the web application. If using the WSGI file for configuration, set it there without committing that file or the secret to the repository; restrict access to the file.
5. Set `OPENAI_MODEL` to a model available to the API key's project. The default is `gpt-4o-mini`.
6. Reload the web app after changing WSGI/environment configuration.
7. Verify the app's AI configuration with `python manage.py check_ai` from a console where the key is available. If it reports missing configuration, verify which environment the web process receives. If it reports HTTP 401/403, create a fresh valid API secret and check project permissions. For HTTP 429, check API quota/billing. For network errors, check host outbound access.

Do not run `seed_demo` on production unless demonstration data is intentionally required. Back up the production database and uploaded media before upgrades.

### Key application paths

| Purpose | Path |
| --- | --- |
| Public homepage | `/` |
| Portal login | `/accounts/login/` |
| Role-specific dashboard | `/accounts/dashboard/` |
| Staff account management | `/accounts/staff/` |
| Student records | `/students/` |
| Archived students | `/students/archived/` |
| Academic calendar and terms | `/academics/` |
| Assignments and quizzes | `/assignments/` |
| Finance and payments | `/finance/` |
| Django administration | `/admin/` |

Use the sidebar and page links for exact operations available to each role. Access checks are enforced server-side; hiding a link does not grant or revoke permissions.

### Routine checks

Run these commands after code changes and before deployment:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check_ai
```

`check_ai` requires a valid, configured key and outbound network. The other three checks do not require AI credentials.
