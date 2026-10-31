from django.db.models import Q, Sum

from .models import Fee, Payment


def active_fees_for_student(student):
    scope = Q(school_class__isnull=True)
    if student.school_class_id:
        scope |= Q(school_class_id=student.school_class_id)
    return Fee.objects.filter(scope, is_active=True).select_related(
        'school_class', 'academic_year'
    )


def fee_totals_for_student(student):
    expected = active_fees_for_student(student).aggregate(
        total=Sum('amount')
    )['total'] or 0
    paid = Payment.objects.filter(student=student).aggregate(
        total=Sum('amount')
    )['total'] or 0
    return expected, paid, max(expected - paid, 0)
