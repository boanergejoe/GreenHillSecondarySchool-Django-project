from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from academics.models import Term


class Examination(models.Model):
    class ExamType(models.TextChoices):
        MIDTERM = 'midterm', 'Midterm'
        FINAL = 'final', 'Final'
        QUIZ = 'quiz', 'Quiz'
        MOCK = 'mock', 'Mock'
        CONTINUOUS = 'continuous', 'Continuous Assessment'

    name = models.CharField(max_length=150)
    exam_type = models.CharField(
        max_length=20, choices=ExamType.choices, default=ExamType.MIDTERM
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear', on_delete=models.CASCADE, related_name='examinations'
    )
    term = models.CharField(
        max_length=50, choices=Term.Name.choices, blank=True, default=''
    )
    school_classes = models.ManyToManyField(
        'academics.SchoolClass', blank=True, related_name='examinations',
        help_text='Select the classes sitting this examination. Leave blank for all classes.',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    total_marks = models.PositiveIntegerField(default=100)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f'{self.name} - {self.academic_year.name}'

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'End date cannot be before the start date.'
        if errors:
            raise ValidationError(errors)

    @property
    def school_class_names(self):
        names = [school_class.name for school_class in self.school_classes.all()]
        return ', '.join(names) if names else 'All classes'

    def get_absolute_url(self):
        return reverse('examinations:exam_detail', args=[self.pk])


class Result(models.Model):
    class Grade(models.TextChoices):
        A = 'A', 'A - Excellent'
        B = 'B', 'B - Very Good'
        C = 'C', 'C - Good'
        D = 'D', 'D - Pass'
        E = 'E', 'E - Weak Pass'
        F = 'F', 'F - Fail'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='results'
    )
    examination = models.ForeignKey(
        Examination, on_delete=models.CASCADE, related_name='results'
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='results'
    )
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    grade = models.CharField(max_length=2, choices=Grade.choices, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='entered_results',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['subject__name']
        unique_together = ('student', 'examination', 'subject')

    def __str__(self):
        return f'{self.student} - {self.subject} - {self.marks_obtained}'

    @property
    def percentage(self):
        if not self.total_marks:
            return 0.0
        return round(float(self.marks_obtained) / float(self.total_marks) * 100, 1)

    @staticmethod
    def compute_grade(percentage):
        if percentage >= 80:
            return Result.Grade.A
        if percentage >= 70:
            return Result.Grade.B
        if percentage >= 60:
            return Result.Grade.C
        if percentage >= 50:
            return Result.Grade.D
        if percentage >= 40:
            return Result.Grade.E
        return Result.Grade.F

    @staticmethod
    def remark_for_percentage(percentage):
        if percentage >= 80:
            return 'Excellent'
        if percentage >= 70:
            return 'Very Good'
        if percentage >= 60:
            return 'Good'
        if percentage >= 50:
            return 'Satisfactory'
        if percentage >= 40:
            return 'Needs Improvement'
        return 'Unsatisfactory'

    @property
    def performance_remark(self):
        if self.remarks and self.remarks.strip():
            return self.remarks.strip()
        return self.remark_for_percentage(self.percentage)

    def save(self, *args, **kwargs):
        if not self.total_marks:
            self.total_marks = self.examination.total_marks if self.examination_id else 100
        self.grade = self.compute_grade(self.percentage)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('examinations:result_list')
