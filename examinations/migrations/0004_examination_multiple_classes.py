from django.db import migrations, models


def copy_class_assignments(apps, schema_editor):
    Examination = apps.get_model('examinations', 'Examination')
    database = schema_editor.connection.alias
    for exam in Examination.objects.using(database).only(
        'pk', 'school_class_id'
    ).iterator():
        if exam.school_class_id:
            exam.school_classes.db_manager(database).add(exam.school_class_id)


def restore_class_assignments(apps, schema_editor):
    Examination = apps.get_model('examinations', 'Examination')
    database = schema_editor.connection.alias
    for exam in Examination.objects.using(database).only('pk').iterator():
        school_class_id = exam.school_classes.using(database).values_list(
            'pk', flat=True
        ).first()
        if school_class_id:
            Examination.objects.using(database).filter(pk=exam.pk).update(
                school_class_id=school_class_id
            )


class Migration(migrations.Migration):

    dependencies = [
        ('examinations', '0003_examination_term_choice'),
    ]

    operations = [
        migrations.AddField(
            model_name='examination',
            name='school_classes',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    'Select the classes sitting this examination. '
                    'Leave blank for all classes.'
                ),
                related_name='examinations_migrating',
                to='academics.schoolclass',
            ),
        ),
        migrations.RunPython(
            copy_class_assignments,
            restore_class_assignments,
        ),
        migrations.RemoveField(
            model_name='examination',
            name='school_class',
        ),
        migrations.AlterField(
            model_name='examination',
            name='school_classes',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    'Select the classes sitting this examination. '
                    'Leave blank for all classes.'
                ),
                related_name='examinations',
                to='academics.schoolclass',
            ),
        ),
    ]
