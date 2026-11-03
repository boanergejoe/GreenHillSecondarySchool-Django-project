import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Parent(models.Model):
    class Relationship(models.TextChoices):
        FATHER = 'father', 'Father'
        MOTHER = 'mother', 'Mother'
        GUARDIAN = 'guardian', 'Guardian'
        OTHER = 'other', 'Other'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_profile'
    )
    occupation = models.CharField(max_length=120, blank=True)
    relationship = models.CharField(
        max_length=20, choices=Relationship.choices, default=Relationship.GUARDIAN
    )
    address = models.TextField(blank=True)
    alternate_phone = models.CharField(max_length=30, blank=True)
    national_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return self.user.display_name

    @property
    def children_count(self):
        return self.children.count()

    def get_absolute_url(self):
        return reverse('students:parent_list')


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        GRADUATED = 'graduated', 'Graduated'
        TRANSFERRED = 'transferred', 'Transferred'
        SUSPENDED = 'suspended', 'Suspended'
        INACTIVE = 'inactive', 'Inactive'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile'
    )
    student_id = models.CharField(max_length=30, unique=True, blank=True)
    school_class = models.ForeignKey(
        'academics.SchoolClass', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='students',
    )
    department = models.ForeignKey(
        'academics.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='students',
    )
    parent = models.ForeignKey(
        Parent, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children',
    )
    admission_date = models.DateField(default=timezone.localdate)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10, choices=Gender.choices, default=Gender.OTHER
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='archived_students',
    )
    archived_user_was_active = models.BooleanField(default=True)
    address = models.TextField(blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=30, blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    medical_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f'{self.user.display_name} ({self.student_id or "new"})'

    def save(self, *args, **kwargs):
        if not self.student_id:
            year = timezone.localdate().year
            self.student_id = f'GSS-{year}-{uuid.uuid4().hex[:5].upper()}'
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.display_name

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def attendance_percentage(self):
        records = self.attendance_records.all()
        total = records.count()
        if not total:
            return 0
        present = records.filter(status__in=['present', 'late']).count()
        return round(present / total * 100, 1)

    def get_absolute_url(self):
        return reverse('students:student_detail', args=[self.pk])


class ReadmissionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='readmission_requests'
    )
    pending_student = models.OneToOneField(
        Student, on_delete=models.CASCADE, null=True, blank=True,
        related_name='pending_readmission_request',
    )
    school_class = models.ForeignKey(
        'academics.SchoolClass', on_delete=models.PROTECT,
        related_name='readmission_requests',
    )
    terms = models.JSONField(default=list)
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_readmission_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} — {self.get_status_display()}'

    def save(self, *args, **kwargs):
        self.pending_student_id = (
            self.student_id if self.status == self.Status.PENDING else None
        )
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'pending_student'}
        super().save(*args, **kwargs)
