import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Fee(models.Model):
    name = models.CharField(max_length=150)
    school_class = models.ForeignKey(
        'academics.SchoolClass', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fees',
    )
    academic_year = models.ForeignKey(
        'academics.AcademicYear', on_delete=models.CASCADE, related_name='fees'
    )
    term = models.ForeignKey(
        'academics.Term', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fees',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-academic_year__start_date', 'name']
        unique_together = ('name', 'school_class', 'academic_year')
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'academic_year'],
                condition=models.Q(school_class__isnull=True),
                name='unique_universal_fee_per_year',
            ),
        ]

    def __str__(self):
        return f'{self.name} - {self.amount:,.2f}'

    @property
    def paid_amount(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or 0

    @property
    def class_scope(self):
        return self.school_class.name if self.school_class_id else 'All classes'

    @property
    def applies_to_all_classes(self):
        return self.school_class_id is None

    def clean(self):
        errors = {}
        if (
            self.academic_year_id and self.school_class_id
            and self.school_class.academic_year_id != self.academic_year_id
        ):
            errors['school_class'] = 'The class must belong to the selected academic year.'
        if (
            self.term_id and self.academic_year_id
            and self.term.academic_year_id != self.academic_year_id
        ):
            errors['term'] = 'The term must belong to the selected academic year.'
        if errors:
            raise ValidationError(errors)

    def get_absolute_url(self):
        return reverse('finance:fee_list')


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK = 'bank', 'Bank Transfer'
        MOBILE = 'mobile', 'Mobile Money'
        CHEQUE = 'cheque', 'Cheque'
        CARD = 'card', 'Card'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='payments'
    )
    fee = models.ForeignKey(
        Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=100, blank=True)
    receipt_number = models.CharField(max_length=30, unique=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recorded_payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'{self.receipt_number} - {self.student} - {self.amount:,.2f}'

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f'RCP-{timezone.localdate().year}-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('finance:payment_detail', args=[self.pk])
