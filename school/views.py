from django.shortcuts import render

from academics.models import AcademicYear, Subject, Term
from communications.models import Announcement


def home(request):
    current_year = AcademicYear.objects.filter(is_current=True).first()
    terms = Term.objects.filter(academic_year=current_year) if current_year else Term.objects.none()
    subject_names = (
        Subject.objects.filter(academic_year=current_year, is_active=True)
        .order_by('name')
        .values_list('name', flat=True)
        if current_year else Subject.objects.none().values_list('name', flat=True)
    )
    curriculum_subjects = {}
    for subject_name in subject_names:
        curriculum_subjects.setdefault(subject_name.strip().casefold(), subject_name.strip())
    news = Announcement.objects.filter(
        is_published=True,
        is_public=True,
    ).order_by('-event_date', '-created_at')[:3]
    return render(request, 'landing/home.html', {
        'current_academic_year': current_year,
        'term_dates': terms.order_by('start_date'),
        'curriculum_subjects': list(curriculum_subjects.values()),
        'public_news': news,
    })


def privacy_policy(request):
    return render(request, 'legal/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'legal/terms_of_service.html')


def cookie_policy(request):
    return render(request, 'legal/cookie_policy.html')


def acceptable_use(request):
    return render(request, 'legal/acceptable_use.html')


def data_protection(request):
    return render(request, 'legal/data_protection.html')


def child_protection(request):
    return render(request, 'legal/child_protection.html')
