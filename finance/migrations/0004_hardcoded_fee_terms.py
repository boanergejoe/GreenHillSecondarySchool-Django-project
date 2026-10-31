from django.db import migrations, models


TERM_CHOICES = [
    ('Term 1', 'Term 1'),
    ('Term 2', 'Term 2'),
    ('Term 3', 'Term 3'),
]


def copy_term_names(apps, schema_editor):
    database = schema_editor.connection.alias
    Fee = apps.get_model('finance', 'Fee')
    for fee in Fee.objects.using(database).select_related('term').iterator():
        fee.term_name = fee.term.name if fee.term_id else ''
        fee.save(update_fields=['term_name'])


def restore_term_links(apps, schema_editor):
    database = schema_editor.connection.alias
    Fee = apps.get_model('finance', 'Fee')
    Term = apps.get_model('academics', 'Term')
    for fee in Fee.objects.using(database).iterator():
        term_id = Term.objects.using(database).filter(
            academic_year_id=fee.academic_year_id,
            name=fee.term_name,
        ).values_list('pk', flat=True).first()
        if term_id:
            fee.term_id = term_id
            fee.save(update_fields=['term'])


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0008_hardcoded_subject_enrollment_terms'),
        ('finance', '0003_rename_semester_to_term'),
    ]

    operations = [
        migrations.AddField(
            model_name='fee',
            name='term_name',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.RunPython(copy_term_names, restore_term_links),
        migrations.RemoveField(
            model_name='fee',
            name='term',
        ),
        migrations.RenameField(
            model_name='fee',
            old_name='term_name',
            new_name='term',
        ),
        migrations.AlterField(
            model_name='fee',
            name='term',
            field=models.CharField(
                blank=True,
                choices=TERM_CHOICES,
                default='',
                max_length=50,
            ),
        ),
    ]
