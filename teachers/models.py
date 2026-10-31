import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Teacher(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        CONTRACT = 'contract', 'Contract'
        VISITING = 'visiting', 'Visiting'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on_leave', 'On Leave'
        INACTIVE = 'inactive', 'Inactive'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_profile'
    )
    staff_id = models.CharField(max_length=30, unique=True, blank=True)
    department = models.ForeignKey(
        'academics.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teachers',
    )
    qualification = models.CharField(max_length=150, blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    date_joined = models.DateField(default=timezone.localdate)
    office = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f'{self.user.display_name} ({self.staff_id or "new"})'

    def save(self, *args, **kwargs):
        if not self.staff_id:
            year = timezone.localdate().year
            self.staff_id = f'GSS-T-{year}-{uuid.uuid4().hex[:4].upper()}'
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.display_name

    @property
    def subject_count(self):
        return self.user.teaching_subjects.count()

    def get_absolute_url(self):
        return reverse('teachers:teacher_detail', args=[self.pk])
