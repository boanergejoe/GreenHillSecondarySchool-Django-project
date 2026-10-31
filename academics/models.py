from django.conf import settings
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


class Semester(models.Model):
    name = models.CharField(max_length=50)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='semesters'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-academic_year__start_date', 'name']
        unique_together = ('name', 'academic_year')

    def __str__(self):
        return f'{self.name} - {self.academic_year.name}'

    def save(self, *args, **kwargs):
        if self.is_current:
            Semester.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('academics:semester_list')


class SchoolClass(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50, blank=True, help_text='e.g. Form 1, Year 2')
    stream = models.CharField(max_length=50, blank=True)
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
        return self.students.filter(status='active').count()

    def get_absolute_url(self):
        return reverse('academics:class_list')


class Course(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='courses',
    )
    description = models.TextField(blank=True)
    credit_units = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def get_absolute_url(self):
        return reverse('academics:course_list')


class Subject(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subjects',
    )
    departments = models.ManyToManyField(
        Department, blank=True, related_name='subjects',
        help_text='Select both Arts and Science for subjects shared by both departments.',
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name='subjects'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teaching_subjects',
        limit_choices_to={'role': 'teacher'},
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='subjects'
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subjects',
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('code', 'school_class', 'academic_year')

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def department_names(self):
        names = [department.name for department in self.departments.all()]
        if names:
            return ', '.join(names)
        if self.course_id and self.course.department_id:
            return self.course.department.name
        return '-'

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
    semester = models.ForeignKey(
        Semester, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enrollments',
    )
    enrolled_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-enrolled_on']
        unique_together = ('student', 'school_class', 'academic_year', 'semester')

    def __str__(self):
        return f'{self.student} - {self.school_class}'

    def get_absolute_url(self):
        return reverse('academics:enrollment_list')
