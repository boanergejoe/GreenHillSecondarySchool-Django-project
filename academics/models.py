from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'

    def get_absolute_url(self):
        return reverse('academics:department_list')


class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('academics:year_list')


class Term(models.Model):
    class Name(models.TextChoices):
        TERM_1 = 'Term 1', 'Term 1'
        TERM_2 = 'Term 2', 'Term 2'
        TERM_3 = 'Term 3', 'Term 3'

    name = models.CharField(max_length=50, choices=Name.choices)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='terms'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-academic_year__start_date', 'name']
        unique_together = ('name', 'academic_year')

    def __str__(self):
        return f'{self.name} - {self.academic_year.name}'

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors['end_date'] = 'End date must be after the start date.'
        if self.academic_year_id:
            if self.start_date and self.start_date < self.academic_year.start_date:
                errors['start_date'] = 'Term start date must fall within the academic year.'
            if self.end_date and self.end_date > self.academic_year.end_date:
                errors['end_date'] = 'Term end date must fall within the academic year.'
            existing_terms = Term.objects.filter(
                academic_year_id=self.academic_year_id
            ).exclude(pk=self.pk)
            if existing_terms.count() >= 3:
                errors['academic_year'] = 'An academic year can have at most three terms.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.is_current:
            Term.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('academics:term_list')


class SchoolClass(models.Model):
    class Level(models.TextChoices):
        SENIOR_1 = 'Senior 1', 'Senior 1'
        SENIOR_2 = 'Senior 2', 'Senior 2'
        SENIOR_3 = 'Senior 3', 'Senior 3'
        SENIOR_4 = 'Senior 4', 'Senior 4'

    class Stream(models.TextChoices):
        ARTS = 'Arts', 'Arts'
        SCIENCE = 'Science', 'Science'

    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50, choices=Level.choices)
    stream = models.CharField(max_length=50, choices=Stream.choices, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='classes',
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='classes'
    )
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_classes',
        limit_choices_to={'role': 'teacher'},
    )
    capacity = models.PositiveIntegerField(default=50)
    room = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'classes'
        unique_together = ('name', 'academic_year')

    def __str__(self):
        return self.name

    @property
    def student_count(self):
        return self.students.filter(status='active', is_archived=False).count()

    def clean(self):
        errors = {}
        streamed_levels = {self.Level.SENIOR_3, self.Level.SENIOR_4}
        if self.level in streamed_levels:
            if self.stream not in self.Stream.values:
                errors['stream'] = 'Senior 3 and Senior 4 classes require an Arts or Science stream.'
            if not self.department_id:
                errors['department'] = 'A streamed class must have a matching department.'
            elif self.department.code.upper() not in {
                'ART' if self.stream == self.Stream.ARTS else 'SCI'
            }:
                errors['department'] = 'The department must match the selected stream.'
        else:
            if self.stream:
                errors['stream'] = 'Only Senior 3 and Senior 4 classes use a stream.'
            if self.department_id:
                errors['department'] = 'Only streamed classes belong to a department.'
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:class_list')


class Subject(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    departments = models.ManyToManyField(
        Department, blank=True, related_name='subjects',
        help_text='Select both Arts and Science for subjects shared by both departments.',
    )
    school_classes = models.ManyToManyField(
        SchoolClass, related_name='subjects'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teaching_subjects',
        limit_choices_to={'role': 'teacher'},
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='subjects'
    )
    term = models.CharField(
        max_length=50, choices=Term.Name.choices, blank=True, default=''
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def department_names(self):
        names = [department.name for department in self.departments.all()]
        return ', '.join(names) if names else '-'

    @property
    def school_class_names(self):
        names = [school_class.name for school_class in self.school_classes.all()]
        return ', '.join(names) if names else '-'

    @property
    def is_dual_department(self):
        return self.departments.count() > 1

    def get_absolute_url(self):
        return reverse('academics:subject_list')


class Enrollment(models.Model):
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='enrollments'
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name='enrollments'
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='enrollments'
    )
    term = models.CharField(
        max_length=50, choices=Term.Name.choices, blank=True, default=''
    )
    enrolled_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-enrolled_on']
        unique_together = ('student', 'school_class', 'academic_year', 'term')

    def __str__(self):
        return f'{self.student} - {self.school_class}'

    def clean(self):
        errors = {}
        if (
            self.academic_year_id and self.school_class_id
            and self.school_class.academic_year_id != self.academic_year_id
        ):
            errors['school_class'] = 'The class must belong to the selected academic year.'
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:enrollment_list')
