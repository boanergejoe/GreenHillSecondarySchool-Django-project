from datetime import date

from django.db import migrations


OLD_TITLE = 'announcenment'
OLD_MESSAGE = (
    'i will like to inform all the student that on monday 25th/dec/2026 '
    'we will not have classes'
)
NEW_TITLE = 'DEMO: Sample class notice'
NEW_MESSAGE = (
    'Demonstration content only. This is not a real notice from the school. '
    'Do not use this sample to make decisions about school dates or class schedules.'
)
DEMO_DATE = date(2026, 11, 30)


def mark_notice_as_demo(apps, schema_editor):
    Announcement = apps.get_model('communications', 'Announcement')
    Announcement.objects.filter(
        title=OLD_TITLE,
        message=OLD_MESSAGE,
        event_date=DEMO_DATE,
    ).update(
        title=NEW_TITLE,
        message=NEW_MESSAGE,
        event_date=None,
    )


def restore_notice(apps, schema_editor):
    Announcement = apps.get_model('communications', 'Announcement')
    Announcement.objects.filter(
        title=NEW_TITLE,
        message=NEW_MESSAGE,
        event_date__isnull=True,
    ).update(
        title=OLD_TITLE,
        message=OLD_MESSAGE,
        event_date=DEMO_DATE,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0002_public_announcement_flag'),
    ]

    operations = [
        migrations.RunPython(mark_notice_as_demo, restore_notice),
    ]
