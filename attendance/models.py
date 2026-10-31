from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        EXCUSED = 'excused', 'Excused'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='attendance_records'
    )
    school_class = models.ForeignKey(
        'academics.SchoolClass', on_delete=models.CASCADE, related_name='attendance_records'
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attendance_records',
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PRESENT
    )
    remarks = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_attendance',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'student__user__first_name']
        unique_together = ('student', 'school_class', 'subject', 'date')
        verbose_name_plural = 'attendance records'

    def __str__(self):
        return f'{self.student} - {self.date} - {self.get_status_display()}'

    @property
    def status_badge(self):
        return {
            self.Status.PRESENT: 'success',
            self.Status.ABSENT: 'danger',
            self.Status.LATE: 'warning',
            self.Status.EXCUSED: 'info',
        }.get(self.status, 'secondary')

    def get_absolute_url(self):
        return reverse('attendance:list')
