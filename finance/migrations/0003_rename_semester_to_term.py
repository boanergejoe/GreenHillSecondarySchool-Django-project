import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0005_rename_semester_to_term'),
        ('finance', '0002_fee_unique_universal_fee_per_year'),
    ]

    operations = [
        migrations.RenameField(
            model_name='fee',
            old_name='semester',
            new_name='term',
        ),
        migrations.AlterField(
            model_name='fee',
            name='term',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='fees',
                to='academics.term',
            ),
        ),
    ]
