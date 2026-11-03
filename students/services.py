from django.db import transaction
from django.utils import timezone

from academics.models import Enrollment, SchoolClass

from .models import Student


@transaction.atomic
def archive_student(student, archived_by):
    student = Student.objects.select_for_update().select_related('user').get(
        pk=student.pk
    )
    if student.is_archived:
        return student

    student.archived_user_was_active = student.user.is_active
    student.archived_at = timezone.now()
    student.archived_by = archived_by
    student.is_archived = True
    student.save(update_fields=[
        'archived_user_was_active',
        'archived_at',
        'archived_by',
        'is_archived',
    ])
    student.user.is_active = False
    student.user.save(update_fields=['is_active'])
    return student


@transaction.atomic
def restore_student(student):
    student = Student.objects.select_for_update().select_related('user').get(
        pk=student.pk
    )
    if not student.is_archived:
        return student

    student.is_archived = False
    student.archived_at = None
    student.archived_by = None
    student.user.is_active = student.archived_user_was_active
    student.archived_user_was_active = True
    student.save(update_fields=[
        'is_archived',
        'archived_at',
        'archived_by',
        'archived_user_was_active',
    ])
    student.user.save(update_fields=['is_active'])
    return student


@transaction.atomic
def apply_readmission(student, school_class, terms, admission_date=None):
    student = Student.objects.select_for_update().select_related('user').get(
        pk=student.pk
    )
    school_class = SchoolClass.objects.select_related(
        'department'
    ).get(pk=school_class.pk)
    admission_date = admission_date or timezone.localdate()

    student.enrollments.filter(is_active=True).update(is_active=False)
    student.school_class = school_class
    student.department = (
        school_class.department
        if school_class.level in (
            SchoolClass.Level.SENIOR_3, SchoolClass.Level.SENIOR_4
        )
        else None
    )
    student.admission_date = admission_date
    student.status = Student.Status.ACTIVE
    student.is_archived = False
    student.archived_at = None
    student.archived_by = None
    student.archived_user_was_active = True
    student.save()
    for term in terms:
        Enrollment.objects.update_or_create(
            student=student,
            school_class=school_class,
            academic_year=school_class.academic_year,
            term=term,
            defaults={
                'enrolled_on': admission_date,
                'is_active': True,
            },
        )
    student.user.is_active = True
    student.user.save(update_fields=['is_active'])
    return student
