import django.db.models.deletion
from django.db import migrations, models


TERM_NAMES = {
    'term 1': 'Term 1',
    'term one': 'Term 1',
    'semester 1': 'Term 1',
    'semester one': 'Term 1',
    'first term': 'Term 1',
    'term 2': 'Term 2',
    'term two': 'Term 2',
    'semester 2': 'Term 2',
    'semester two': 'Term 2',
    'second term': 'Term 2',
    'term 3': 'Term 3',
    'term three': 'Term 3',
    'semester 3': 'Term 3',
    'semester three': 'Term 3',
    'third term': 'Term 3',
}
LEVELS = ('Senior 1', 'Senior 2', 'Senior 3', 'Senior 4')


def normalize_terms_and_classes(apps, schema_editor):
    Term = apps.get_model('academics', 'Term')
    SchoolClass = apps.get_model('academics', 'SchoolClass')
    Department = apps.get_model('academics', 'Department')

    for term in Term.objects.all():
        normalized = TERM_NAMES.get(term.name.strip().lower())
        if not normalized or normalized == term.name:
            continue
        collision = Term.objects.filter(
            academic_year_id=term.academic_year_id, name=normalized
        ).exclude(pk=term.pk).exists()
        if not collision:
            term.name = normalized
            term.save(update_fields=['name'])

    arts, _ = Department.objects.get_or_create(
        code='ART',
        defaults={
            'name': 'Arts',
            'description': 'Languages, humanities and social sciences.',
        },
    )
    science, _ = Department.objects.get_or_create(
        code='SCI',
        defaults={
            'name': 'Science',
            'description': 'Science and mathematics subjects.',
        },
    )

    for school_class in SchoolClass.objects.all():
        level = (school_class.level or '').strip()
        if level not in LEVELS:
            for candidate in LEVELS:
                if school_class.name.lower().startswith(candidate.lower()):
                    school_class.level = candidate
                    break

        if school_class.level in ('Senior 3', 'Senior 4'):
            stream = (school_class.stream or '').strip().lower()
            if stream in {'arts', 'art'}:
                school_class.stream = 'Arts'
                school_class.department_id = arts.pk
            elif stream in {'science', 'sciences', 'sci'}:
                school_class.stream = 'Science'
                school_class.department_id = science.pk
            elif school_class.department_id:
                department = Department.objects.filter(
                    pk=school_class.department_id
                ).first()
                if department and department.code.upper() == 'ART':
                    school_class.stream = 'Arts'
                else:
                    school_class.stream = 'Science'
                    school_class.department_id = science.pk
            else:
                school_class.stream = 'Arts'
                school_class.department_id = arts.pk

            target_name = f'{school_class.level} {school_class.stream}'
            if 'arts' not in school_class.name.lower() and 'science' not in school_class.name.lower():
                collision = SchoolClass.objects.filter(
                    name=target_name,
                    academic_year_id=school_class.academic_year_id,
                ).exclude(pk=school_class.pk).exists()
                if not collision:
                    school_class.name = target_name
        else:
            school_class.stream = ''
            school_class.department_id = None

        school_class.save()


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0004_link_subject_departments'),
        ('examinations', '0001_initial'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(old_name='Semester', new_name='Term'),
        migrations.RenameField(
            model_name='subject',
            old_name='semester',
            new_name='term',
        ),
        migrations.RenameField(
            model_name='enrollment',
            old_name='semester',
            new_name='term',
        ),
        migrations.AlterUniqueTogether(
            name='enrollment',
            unique_together={('student', 'school_class', 'academic_year', 'term')},
        ),
        migrations.AlterField(
            model_name='term',
            name='name',
            field=models.CharField(
                choices=[('Term 1', 'Term 1'), ('Term 2', 'Term 2'), ('Term 3', 'Term 3')],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='term',
            name='academic_year',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='terms',
                to='academics.academicyear',
            ),
        ),
        migrations.RunPython(
            normalize_terms_and_classes,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='schoolclass',
            name='level',
            field=models.CharField(
                choices=[
                    ('Senior 1', 'Senior 1'),
                    ('Senior 2', 'Senior 2'),
                    ('Senior 3', 'Senior 3'),
                    ('Senior 4', 'Senior 4'),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='schoolclass',
            name='stream',
            field=models.CharField(
                blank=True,
                choices=[('Arts', 'Arts'), ('Science', 'Science')],
                max_length=50,
            ),
        ),
    ]
