from decimal import Decimal

from django.db.models import Q, Sum

from academics.models import AcademicYear

from .models import Fee, Payment


def active_fees_for_student(student):
    scope = Q(school_class__isnull=True)
    if student.school_class_id:
        scope |= Q(school_class_id=student.school_class_id)
    fees = Fee.objects.filter(scope, is_active=True)
    academic_year_id = (
        student.school_class.academic_year_id if student.school_class_id else None
    )
    if not academic_year_id:
        academic_year_id = AcademicYear.objects.filter(
            is_current=True
        ).values_list('pk', flat=True).first()
    if academic_year_id:
        fees = fees.filter(academic_year_id=academic_year_id)
    return fees.select_related('school_class', 'academic_year')


def fee_totals_for_student(student):
    fees = list(active_fees_for_student(student))
    expected = sum((fee.amount for fee in fees), Decimal('0'))
    paid_by_fee = dict(
        Payment.objects.filter(student=student, fee__in=fees)
        .values('fee_id')
        .annotate(total=Sum('amount'))
        .values_list('fee_id', 'total')
    )
    paid = Decimal('0')
    balance = Decimal('0')
    for fee in fees:
        fee_paid = paid_by_fee.get(fee.pk, Decimal('0'))
        paid += min(fee_paid, fee.amount)
        balance += max(fee.amount - fee_paid, Decimal('0'))
    return expected, paid, balance


def exam_eligibility_for_student(student):
    expected, paid, balance = fee_totals_for_student(student)
    has_fees = active_fees_for_student(student).exists()
    return {
        'eligible': has_fees and balance == 0,
        'has_fees': has_fees,
        'expected': expected,
        'paid': paid,
        'balance': balance,
    }
