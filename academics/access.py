from django.db.models import Q

from .models import SchoolClass, Subject


def teacher_classes(user):
    return SchoolClass.objects.filter(
        Q(subjects__teacher=user)
        | Q(class_teacher=user)
        | Q(assigned_teachers__user=user)
    ).distinct()


def teacher_class_ids(user):
    return teacher_classes(user).values_list('pk', flat=True)


def teacher_subjects(user):
    return Subject.objects.filter(
        Q(teacher=user)
        | Q(school_classes__class_teacher=user)
        | Q(school_classes__assigned_teachers__user=user)
    ).distinct()


def teacher_can_access_student(user, student):
    if not student.school_class_id:
        return False
    return teacher_classes(user).filter(pk=student.school_class_id).exists()


def teacher_can_manage_assignment(user, assignment):
    subject = assignment.subject
    return (
        assignment.created_by_id == user.id
        or subject.teacher_id == user.id
        or subject.school_classes.filter(class_teacher_id=user.id).exists()
        or subject.school_classes.filter(assigned_teachers__user=user).exists()
    )
