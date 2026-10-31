from django.conf import settings
from django.db import models
from django.urls import reverse


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = 'all', 'Everyone'
        STUDENTS = 'students', 'Students'
        TEACHERS = 'teachers', 'Teachers'
        PARENTS = 'parents', 'Parents'
        ACCOUNTANTS = 'accountants', 'Accountants'

    title = models.CharField(max_length=200)
    message = models.TextField()
    audience = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.ALL
    )
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    event_date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='announcements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('communications:announcement_list')


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.title}'

    def get_absolute_url(self):
        return reverse('communications:notification_list')
