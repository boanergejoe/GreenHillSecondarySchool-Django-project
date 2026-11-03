from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Assignment(models.Model):
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='assignments'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to='assignments/', blank=True, null=True)
    due_date = models.DateTimeField()
    max_score = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_assignments'
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return timezone.now() > self.due_date

    @property
    def submission_count(self):
        return self.submissions.count()

    def get_absolute_url(self):
        return reverse('assignments:detail', args=[self.pk])


class Submission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWED = 'reviewed', 'Reviewed'
        LATE = 'late', 'Late'
        GRADED = 'graded', 'Graded'

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name='submissions'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='submissions'
    )
    file = models.FileField(upload_to='submissions/', blank=True, null=True)
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUBMITTED
    )
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_submissions',
    )

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f'{self.assignment} - {self.student}'

    def get_absolute_url(self):
        return reverse('assignments:detail', args=[self.assignment_id])


class Quiz(models.Model):
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='quizzes'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_quizzes'
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class QuizQuestion(models.Model):
    class Choice(models.IntegerChoices):
        A = 0, 'A'
        B = 1, 'B'
        C = 2, 'C'
        D = 3, 'D'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    prompt = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.PositiveSmallIntegerField(choices=Choice.choices)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['position', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['quiz', 'position'], name='unique_quiz_question_position'
            )
        ]

    def __str__(self):
        return f'{self.quiz.title}: question {self.position}'

    @property
    def options(self):
        return [self.option_a, self.option_b, self.option_c, self.option_d]


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='quiz_attempts'
    )
    answers = models.JSONField(default=dict)
    score = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['quiz', 'student'], name='unique_student_quiz_attempt'
            )
        ]

    def __str__(self):
        return f'{self.student} - {self.quiz}'

    @property
    def total_questions(self):
        return self.quiz.questions.count()
