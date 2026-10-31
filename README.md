# Green Hill Secondary School Management System

A Django-based college and high school management system for **Green Hill Secondary School**, Central Equatoria State, P.O. Box 405, Gudele South, Juba, South Sudan. Telephone: +211 911 743 302 / +211 923 580 596. It provides role-based dashboards and school operations for administrators, teachers, students, parents, and accountants.

## Features

- Role-based authentication and dashboards for administrators, teachers, students, parents, and accountants.
- Student registration, parent/guardian records, automatic student IDs, student promotion, and profile pages.
- Teacher records, departments, staff accounts, and role assignment.
- Academic years, terms, classes, courses, subjects, and enrollments.
- Attendance capture, filtering, summaries, and reporting.
- Examinations, result entry, result lists, report cards, and PDF report cards.
- Fee structures, payments, receipts, fee statements, and financial overview.
- Assignments, student submissions, and teacher review/grading.
- Announcements and user notifications.
- Excel and PDF exports for students, teachers, attendance, results, and finance.
- Responsive Bootstrap 5 interface with dashboards and charts.
- Public premium landing page at `/` with the uploaded school logo, animated sections, testimonials, role overviews, and accessible navigation.
- Create forms enforce all visible fields as required, excluding generated IDs, checkboxes, and file uploads.

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

Open `http://127.0.0.1:8000/` for the public landing page, then use **Login** or **Get Started** to access the management system.

The included `db.sqlite3` already contains demo data. Both `migrate` and `seed_demo` are safe to run again.

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

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Development key | Production secret key |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
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

The integration suite covers the public landing page, required-field create validation, role dashboards, management pages, role-based access restrictions, linked user creation for students/teachers/parents, report exports, receipts, and PDF report cards.

```powershell
python manage.py test
```

## Project Structure

```text
greenhill/          Project settings and root URL configuration
accounts/           Authentication, custom user model, dashboards, staff accounts
students/           Student and parent records, promotion
teachers/           Teacher records and departments
academics/          Academic years, terms, classes, courses, subjects, enrollments
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

## Production Notes

- Set a strong `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=False`.
- Configure `DJANGO_ALLOWED_HOSTS` with the deployed domain or IP.
- Use MySQL and run `migrate` against the production database.
- Run `python manage.py collectstatic` and serve `staticfiles/` and `media/` through the web server.
- Serve the application with a production WSGI server behind HTTPS.
- Change all demo passwords before real use.
- Keep database backups and uploaded media outside the application release directory.
