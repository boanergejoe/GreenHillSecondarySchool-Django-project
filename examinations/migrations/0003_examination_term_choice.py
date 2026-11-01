from django.db import migrations, models


TERM_CHOICES = [
    ('Term 1', 'Term 1'),
    ('Term 2', 'Term 2'),
    ('Term 3', 'Term 3'),
]


def copy_term_names(apps, schema_editor):
    Examination = apps.get_model('examinations', 'Examination')
    database = schema_editor.connection.alias
    for exam in Examination.objects.using(database).select_related('term').iterator():
        if exam.term_id:
            exam.term_name = exam.term.name
            exam.save(using=database, update_fields=['term_name'])


def restore_term_relations(apps, schema_editor):
    Examination = apps.get_model('examinations', 'Examination')
    Term = apps.get_model('academics', 'Term')
    database = schema_editor.connection.alias
    for exam in Examination.objects.using(database).iterator():
        term = Term.objects.using(database).filter(
            academic_year_id=exam.academic_year_id,
            name=exam.term_name,
        ).first()
        if term:
            exam.term = term
            exam.save(using=database, update_fields=['term'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0008_hardcoded_subject_enrollment_terms'),
        ('examinations', '0002_rename_semester_to_term'),
    ]

    operations = [
        migrations.AddField(
            model_name='examination',
            name='term_name',
            field=models.CharField(
                blank=True,
                choices=TERM_CHOICES,
                default='',
                max_length=50,
            ),
        ),
        migrations.RunPython(copy_term_names, restore_term_relations),
        migrations.RemoveField(
            model_name='examination',
            name='term',
        ),
        migrations.RenameField(
            model_name='examination',
            old_name='term_name',
            new_name='term',
        ),
    ]
