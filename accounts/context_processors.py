from django.conf import settings


def school_context(request):
    unread = 0
    student_profile = None
    teacher_profile = None
    parent_profile = None
    if request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False).count()
        student_profile = getattr(request.user, 'student_profile', None)
        teacher_profile = getattr(request.user, 'teacher_profile', None)
        parent_profile = getattr(request.user, 'parent_profile', None)
    return {
        'school_name': settings.SCHOOL_NAME,
        'school_location': settings.SCHOOL_LOCATION,
        'school_address': settings.SCHOOL_ADDRESS,
        'school_motto': settings.SCHOOL_MOTTO,
        'school_email': settings.SCHOOL_EMAIL,
        'school_phone': settings.SCHOOL_PHONE,
        'school_phone_primary': settings.SCHOOL_PHONE_PRIMARY,
        'school_phone_secondary': settings.SCHOOL_PHONE_SECONDARY,
        'unread_notifications': unread,
        'student_profile': student_profile,
        'teacher_profile': teacher_profile,
        'parent_profile': parent_profile,
    }
