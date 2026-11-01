# Green Hill Secondary School Management System

A Django-based college and high school management system for **Green Hill Secondary School**, Central Equatoria State, P.O. Box 405, Gudele South, Juba, South Sudan. Telephone: +211 911 743 302 / +211 923 580 596. It provides role-based dashboards and school operations for administrators, teachers, students, parents, and accountants.

## Features

- Role-based authentication and dashboards for administrators, teachers, students, parents, and accountants.
- Student registration with independent class and department assignments, parent/guardian records, automatic student IDs, student promotion, and profile pages.
- Teacher records with required multi-class teaching assignments, departments, staff accounts, and role assignment.
- Academic years with three fixed term names, streamed Senior 3/4 classes, subjects, and student enrollments across selected terms.
- Subjects can be assigned to multiple school classes and departments.
- Class-specific fee structures, including differentiated Senior 3/4 tuition pricing.
- Attendance capture, filtering, summaries, and reporting.
- Examinations, result entry, result lists, report cards, and PDF report cards.
- Fee structures, payments, receipts, fee statements, and financial overview.
- Assignments, student submissions, and teacher review/grading.
- Announcements and user notifications; published announcements can be explicitly marked for the public homepage.
- Excel and PDF exports for students, teachers, attendance, results, and finance.
- Responsive Bootstrap 5 interface with dashboards and charts.
- Official school homepage at `/` with admissions guidance, term dates, current subjects, public school news, and school contact information; it does not present sample dashboard figures as live statistics.
- Public legal pages for privacy, terms, cookies, acceptable use, data protection, and child protection, with a cookie-consent banner.
- Create forms enforce all visible fields as required, excluding generated IDs, checkboxes, file uploads, and optional class stream/teacher fields.

## Technology Stack

- Python 3.12+ (validated on Python 3.14.6)
- Django 6.1.2
- SQLite for local/demo use
- MySQL via PyMySQL for production
- Bootstrap 5 and Bootstrap Icons
- Chart.js
- openpyxl for Excel exports
- ReportLab for PDF exports

## Quick Start

From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the public school homepage, then use **Portal Login** to access the management system.

The local `db.sqlite3` is excluded from Git. Run both `migrate` and `seed_demo` to create it and populate the demo data; both commands are safe to run again.

## Demo Accounts

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `Admin@12345` |
| Accountant | `accountant` | `Account@12345` |
| Teacher | `teacher1` | `Teacher@12345` |
| Student | `student1` | `Student@12345` |
| Parent | `parent1` | `Parent@12345` |

Additional seeded teachers include `teacher2`, `teacher3`, and `teacher4`. Additional seeded students and parents are also available for testing role-based access.

The Django administration site is available at `/admin/`.

## Database Configuration

SQLite is used by default. To use MySQL, create a database with `utf8mb4` support and set:

```powershell
$env:DB_ENGINE = "mysql"
$env:DB_NAME = "greenhill_school"
$env:DB_USER = "root"
$env:DB_PASSWORD = "your-password"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
```

Then run:

```powershell
python manage.py migrate
python manage.py seed_demo
```

Term 1, Term 2, and Term 3 are fixed choices in the application code, including for fee records; fee term options do not depend on term rows being present in the production database. Add or edit an academic year from Academic Calendar to enter that year's three optional term date ranges in the same form. The separate Terms list remains available to manage terms individually. Academic years, term dates, classes, subjects, student enrollments, and all other records are stored in the database, not in the deployed source files. For hosting, use a persistent production database and keep its connection settings stable; an ephemeral SQLite file may be replaced when the host rebuilds or restarts the application. Do not run `seed_demo` in production unless demo records are wanted.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Development key | Required, strong production secret key |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated HTTPS origins, for example `https://school.pythonanywhere.com` |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `True` when `DJANGO_DEBUG=False` | Trust the proxy HTTPS scheme header |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` when debug is off | Force HTTPS |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` | HSTS lifetime; set `0` while testing |
| `DJANGO_EMAIL_BACKEND` | Console backend | Use `django.core.mail.backends.smtp.EmailBackend` for SMTP |
| `DJANGO_EMAIL_HOST` | empty | SMTP server |
| `DJANGO_EMAIL_PORT` | `587` | SMTP port |
| `DJANGO_EMAIL_USE_TLS` | `True` | Use TLS for SMTP |
| `DJANGO_EMAIL_HOST_USER` | empty | SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | empty | SMTP password |
| `DJANGO_DEFAULT_FROM_EMAIL` | School email | Default sender address |
| `DB_ENGINE` | `sqlite` | Set to `mysql` for MySQL |
| `DB_NAME` | `greenhill_school` | MySQL database name |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | empty | MySQL password |
| `DB_HOST` | `127.0.0.1` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |

## Management Commands

```powershell
python manage.py seed_demo
python manage.py check
python manage.py test
python manage.py collectstatic
```

`seed_demo` creates or updates the demo academic year, classes, subjects, staff, students, parents, fees, payments, examinations, results, attendance, assignments, submissions, announcements, and notifications.

## Testing

The integration suite covers the school homepage and public-news visibility, legal pages, student health-data access, required-field create validation, term limits and dates, streamed classes, differentiated tuition fees, role dashboards, attendance, fee payments and receipts, published-result access, management pages, role-based access restrictions, linked user creation for students/teachers/parents, report exports, and PDF report cards.

```powershell
python manage.py test
```

## Project Structure

```text
greenhill/          Project settings and root URL configuration
accounts/           Authentication, custom user model, dashboards, staff accounts
students/           Student and parent records, promotion
teachers/           Teacher records and departments
academics/          Academic years, terms, classes, subjects, enrollments
attendance/         Attendance entry, lists, and reports
examinations/       Examinations, results, report cards
finance/            Fees, payments, receipts, statements, overview
assignments/        Assignments, submissions, grading
communications/     Announcements and notifications
reports/            Excel/PDF exports and class performance
school/             Shared views, generic CRUD helpers, seed command, integration tests
templates/          Shared and app-specific templates
static/             CSS and JavaScript assets
media/              Uploaded profile photos and files
```

## GitHub and PythonAnywhere Deployment

### 1. Push the project to GitHub

Keep generated and private files out of Git. The included `.gitignore` excludes the virtual environment, SQLite database, `.env`, uploaded media, and collected static files.

```powershell
git add .
git commit -m "Prepare Green Hill school system for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

### 2. Set up PythonAnywhere

Open a PythonAnywhere Bash console and clone the repository:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git greenhill
cd greenhill
mkvirtualenv --python=/usr/bin/python3.13 greenhill-venv
pip install -r requirements.txt
```

Use the Python version available on your PythonAnywhere account. Django 6.1 requires Python 3.12 or newer.

Create the production environment variables in the Web tab, or set them inside the PythonAnywhere WSGI file:

```python
import os
import sys

path = '/home/YOUR_USERNAME/greenhill'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'greenhill.settings'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_SECRET_KEY'] = 'replace-with-a-long-random-secret-key'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'YOUR_USERNAME.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = 'https://YOUR_USERNAME.pythonanywhere.com'
os.environ['DJANGO_TRUST_X_FORWARDED_PROTO'] = 'True'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

In the PythonAnywhere **Web** tab:

- Set the source directory to `/home/YOUR_USERNAME/greenhill`.
- Set the virtualenv to `/home/YOUR_USERNAME/.virtualenvs/greenhill-venv`.
- Use the WSGI configuration above.
- Add static mapping `/static/` to `/home/YOUR_USERNAME/greenhill/staticfiles`.
- Add media mapping `/media/` to `/home/YOUR_USERNAME/greenhill/media`.
- Enable HTTPS for the site, then reload it.

Run the database and static-file setup:

```bash
workon greenhill-venv
cd ~/greenhill
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

`seed_demo` is optional on production; use it only if you intentionally want the demonstration students, accounts, and passwords.

### 3. Deploy updates

```bash
cd ~/greenhill
git pull
workon greenhill-venv
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then click **Reload** in the PythonAnywhere Web tab. The Django admin is available at `/admin/`.

## Production Notes

- Set a strong `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=False`. The project raises a configuration error if the development key is used with debug disabled.
- Configure `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` with the deployed domain.
- Use MySQL when it is available on the hosting plan. SQLite works for a low-traffic demonstration but can lock under concurrent writes.
- Run `python manage.py collectstatic` and serve `staticfiles/` and `media/` through the web server.
- With `DJANGO_DEBUG=False`, the project enables HTTPS redirects, secure cookies, HSTS, and content-type protection.
- Set `DJANGO_SECURE_HSTS_SECONDS=0` until HTTPS is confirmed stable, then enable a long HSTS lifetime.
- Review and customize the public legal policies with the school's approved wording before production use.
- Change all demo passwords before real use.
- Back up the production database and uploaded media regularly.
