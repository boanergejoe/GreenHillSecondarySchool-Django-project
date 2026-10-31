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
    return fees.select_related('school_class', 'academic_year', 'term')


def fee_totals_for_student(student):
    expected = active_fees_for_student(student).aggregate(
        total=Sum('amount')
    )['total'] or 0
    paid = Payment.objects.filter(student=student).aggregate(
        total=Sum('amount')
    )['total'] or 0
    return expected, paid, max(expected - paid, 0)
