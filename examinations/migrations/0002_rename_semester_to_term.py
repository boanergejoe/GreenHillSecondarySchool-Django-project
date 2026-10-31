import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0005_rename_semester_to_term'),
        ('examinations', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='examination',
            old_name='semester',
            new_name='term',
        ),
        migrations.AlterField(
            model_name='examination',
            name='term',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='examinations',
                to='academics.term',
            ),
        ),
    ]
