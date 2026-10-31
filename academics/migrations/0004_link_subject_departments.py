from django.db import migrations
from django.db.models import Q


COMMON_CODES = {'MATH', 'ENG', 'ICT', 'MAT', 'ENGLISH'}
SCIENCE_CODES = {'BIO', 'BIOLOGY', 'CHEM', 'CHEMISTRY', 'PHY', 'PHYSICS', 'SCI'}


def link_subject_departments(apps, schema_editor):
    Department = apps.get_model('academics', 'Department')
    Subject = apps.get_model('academics', 'Subject')

    arts = Department.objects.filter(
        Q(name__iexact='Arts') | Q(code__iexact='ART')
    ).first()
    if not arts:
        arts = Department.objects.create(
            name='Arts', code='ART',
            description='Languages, humanities and social sciences.',
        )

    science = Department.objects.filter(
        Q(name__iexact='Science') | Q(name__iexact='Sciences')
        | Q(code__iexact='SCI')
    ).first()
    if not science:
        science = Department.objects.create(
            name='Science', code='SCI',
            description='Science and mathematics subjects.',
        )
    elif science.name != 'Science':
        science.name = 'Science'
        science.save(update_fields=['name'])
    science.refresh_from_db()

    for subject in Subject.objects.select_related('course').all():
        code = (
            subject.course.code if subject.course_id else subject.code
        ).upper()
        name = subject.name.lower()
        if code in COMMON_CODES or name in {
            'mathematics', 'english', 'english language', 'ict',
            'information and communication technology',
        }:
            subject.departments.set([arts.pk, science.pk])
        elif code in SCIENCE_CODES or any(
            word in name for word in ('biology', 'chemistry', 'physics', 'science')
        ):
            subject.departments.set([science.pk])
        else:
            subject.departments.set([arts.pk])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0003_subject_departments'),
    ]

    operations = [
        migrations.RunPython(link_subject_departments, migrations.RunPython.noop),
    ]
