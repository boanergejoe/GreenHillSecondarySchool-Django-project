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


class SyllabusCoverage(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='syllabus_coverage'
    )
    term = models.CharField(max_length=50, choices=Term.Name.choices)
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name='syllabus_coverage'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='syllabus_coverage'
    )
    topics_planned = models.PositiveIntegerField(default=1)
    topics_completed = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_syllabus_coverage',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['school_class__name', 'subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=('academic_year', 'term', 'school_class', 'subject'),
                name='unique_syllabus_coverage_per_class_term',
            ),
        ]
        verbose_name_plural = 'syllabus coverage records'

    def __str__(self):
        return f'{self.subject} - {self.school_class} - {self.term}'

    @property
    def completion_percentage(self):
        if not self.topics_planned:
            return 0
        return round(self.topics_completed / self.topics_planned * 100, 1)

    def clean(self):
        errors = {}
        if self.school_class_id and self.academic_year_id:
            if self.school_class.academic_year_id != self.academic_year_id:
                errors['school_class'] = (
                    'The class must belong to the selected academic year.'
                )
        if self.subject_id and self.academic_year_id:
            if self.subject.academic_year_id != self.academic_year_id:
                errors['subject'] = (
                    'The subject must belong to the selected academic year.'
                )
        if self.subject_id and self.school_class_id:
            if not self.subject.school_classes.filter(pk=self.school_class_id).exists():
                errors['subject'] = (
                    'The subject must be assigned to the selected class.'
                )
        if self.topics_planned and self.topics_completed > self.topics_planned:
            errors['topics_completed'] = (
                'Completed topics cannot exceed the number planned.'
            )
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:syllabus_coverage_list')


class LessonPlan(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REVISION = 'revision', 'Revision requested'

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='lesson_plans'
    )
    term = models.CharField(max_length=50, choices=Term.Name.choices)
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name='lesson_plans'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='lesson_plans'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='lesson_plans',
        limit_choices_to={'role': 'teacher'},
    )
    lesson_date = models.DateField()
    topic = models.CharField(max_length=200)
    objectives = models.TextField()
    resources = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_lesson_plans',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-lesson_date', 'school_class__name', 'subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=('teacher', 'school_class', 'subject', 'lesson_date', 'topic'),
                name='unique_teacher_lesson_plan_topic',
            ),
        ]

    def __str__(self):
        return f'{self.topic} - {self.subject} - {self.lesson_date}'

    def clean(self):
        errors = {}
        if self.school_class_id and self.academic_year_id:
            if self.school_class.academic_year_id != self.academic_year_id:
                errors['school_class'] = (
                    'The class must belong to the selected academic year.'
                )
        if self.subject_id and self.academic_year_id:
            if self.subject.academic_year_id != self.academic_year_id:
                errors['subject'] = (
                    'The subject must belong to the selected academic year.'
                )
        if self.subject_id and self.school_class_id:
            if not self.subject.school_classes.filter(pk=self.school_class_id).exists():
                errors['subject'] = (
                    'The subject must be assigned to the selected class.'
                )
        if self.teacher_id and self.subject_id and self.school_class_id:
            from .access import teacher_subjects

            if not teacher_subjects(self.teacher).filter(
                pk=self.subject_id,
                school_classes=self.school_class_id,
            ).exists():
                errors['teacher'] = 'The teacher is not assigned to this subject and class.'
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:lesson_plan_list')


class TeachingObservation(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='teaching_observations',
        limit_choices_to={'role': 'teacher'},
    )
    observer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='conducted_teaching_observations',
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teaching_observations',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teaching_observations',
    )
    observed_on = models.DateField(default=timezone.localdate)
    lesson_prepared = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField()
    strengths = models.TextField()
    improvement_areas = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-observed_on', 'teacher__first_name']

    def __str__(self):
        return f'{self.teacher} - {self.observed_on} ({self.rating}/5)'

    def clean(self):
        errors = {}
        if self.rating and not 1 <= self.rating <= 5:
            errors['rating'] = 'Rating must be between 1 and 5.'
        if self.subject_id and self.school_class_id:
            if not self.subject.school_classes.filter(pk=self.school_class_id).exists():
                errors['subject'] = (
                    'The subject must be assigned to the selected class.'
                )
        if errors:
            raise ValidationError(errors)


class TeacherAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'
        EXCUSED = 'excused', 'Excused'

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='teacher_attendance_records',
        limit_choices_to={'role': 'teacher'},
    )
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=8, choices=Status.choices)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_teacher_attendance',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'teacher__first_name', 'teacher__last_name']
        constraints = [
            models.UniqueConstraint(
                fields=('teacher', 'date'),
                name='unique_teacher_attendance_per_day',
            ),
        ]

    def __str__(self):
        return f'{self.teacher} - {self.date} ({self.get_status_display()})'

    def clean(self):
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError({
                'check_out': 'Check-out time must be after check-in time.',
            })


class AcademicAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='academic_audit_events',
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64, blank=True)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'academic audit event'
        verbose_name_plural = 'academic audit events'

    def __str__(self):
        return f'{self.action}: {self.summary[:80]}'


class TeachingSchedule(models.Model):
    class Weekday(models.TextChoices):
        MONDAY = 'monday', 'Monday'
        TUESDAY = 'tuesday', 'Tuesday'
        WEDNESDAY = 'wednesday', 'Wednesday'
        THURSDAY = 'thursday', 'Thursday'
        FRIDAY = 'friday', 'Friday'
        SATURDAY = 'saturday', 'Saturday'

    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='teaching_schedules'
    )
    term = models.CharField(max_length=50, choices=Term.Name.choices)
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name='teaching_schedules'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='teaching_schedules'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='teaching_schedules',
        limit_choices_to={'role': 'teacher'},
    )
    weekday = models.CharField(max_length=12, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['weekday', 'start_time', 'school_class__name']

    def __str__(self):
        return f'{self.weekday}: {self.subject} - {self.school_class}'

    def clean(self):
        errors = {}
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            errors['end_time'] = 'End time must be after start time.'
        if self.school_class_id and self.academic_year_id:
            if self.school_class.academic_year_id != self.academic_year_id:
                errors['school_class'] = (
                    'The class must belong to the selected academic year.'
                )
        if self.subject_id and self.academic_year_id:
            if self.subject.academic_year_id != self.academic_year_id:
                errors['subject'] = (
                    'The subject must belong to the selected academic year.'
                )
        if self.subject_id and self.school_class_id:
            if not self.subject.school_classes.filter(pk=self.school_class_id).exists():
                errors['subject'] = (
                    'The subject must be assigned to the selected class.'
                )
        if self.teacher_id and self.subject_id and self.school_class_id:
            from .access import teacher_subjects

            if not teacher_subjects(self.teacher).filter(
                pk=self.subject_id,
                school_classes=self.school_class_id,
            ).exists():
                errors['teacher'] = (
                    'The teacher must be assigned to this subject and class.'
                )
        if (
            self.weekday and self.start_time and self.end_time
            and self.school_class_id and self.teacher_id
        ):
            conflicts = TeachingSchedule.objects.filter(
                weekday=self.weekday,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).filter(
                models.Q(teacher_id=self.teacher_id)
                | models.Q(school_class_id=self.school_class_id)
                | (
                    models.Q(room__iexact=self.room.strip())
                    if self.room.strip() else models.Q(pk__in=[])
                )
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                errors['start_time'] = (
                    'This period overlaps another class or teacher schedule.'
                )
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:teaching_schedule_list')


class ExaminationSession(models.Model):
    examination = models.ForeignKey(
        'examinations.Examination', on_delete=models.CASCADE,
        related_name='sessions',
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name='examination_sessions'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name='examination_sessions'
    )
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=100)
    invigilators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='invigilated_exam_sessions',
        limit_choices_to={'role': 'teacher'},
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_examination_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'start_time', 'school_class__name']

    def __str__(self):
        return f'{self.examination.name}: {self.subject} - {self.exam_date}'

    @property
    def invigilator_names(self):
        names = [teacher.display_name for teacher in self.invigilators.all()]
        return ', '.join(names) if names else 'Not assigned'

    @property
    def time_range(self):
        return f'{self.start_time:%H:%M}–{self.end_time:%H:%M}'

    def clean(self):
        errors = {}
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            errors['end_time'] = 'End time must be after start time.'
        if self.examination_id and self.exam_date:
            if not self.examination.start_date <= self.exam_date <= self.examination.end_date:
                errors['exam_date'] = (
                    'The session date must fall within the examination dates.'
                )
        if self.examination_id and self.school_class_id:
            if self.school_class.academic_year_id != self.examination.academic_year_id:
                errors['school_class'] = (
                    'The class must belong to the examination academic year.'
                )
            exam_classes = self.examination.school_classes.all()
            if exam_classes.exists() and not exam_classes.filter(
                pk=self.school_class_id
            ).exists():
                errors['school_class'] = (
                    'The class is not included in this examination.'
                )
        if self.subject_id and self.school_class_id:
            if not self.subject.school_classes.filter(pk=self.school_class_id).exists():
                errors['subject'] = (
                    'The subject must be assigned to the selected class.'
                )
            elif (
                self.examination_id
                and self.subject.academic_year_id != self.examination.academic_year_id
            ):
                errors['subject'] = (
                    'The subject must belong to the examination academic year.'
                )
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('academics:examination_schedule_list')
