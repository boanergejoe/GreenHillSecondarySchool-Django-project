import hashlib
import json

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, Subject, Term
from communications.models import Announcement
from .ai import AIServiceError, answer_school_question


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


@require_POST
def school_assistant(request):
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    visitor_key = hashlib.sha256(ip_address.encode('utf-8')).hexdigest()
    cache_key = f'school-assistant:{visitor_key}'
    try:
        request_count = cache.get(cache_key, 0)
        if request_count >= 10:
            return JsonResponse(
                {'error': 'Too many questions. Please try again later.'},
                status=429,
            )
        cache.set(cache_key, request_count + 1, timeout=3600)
    except (TypeError, ValueError):
        return JsonResponse(
            {'error': 'The assistant is temporarily unavailable. Please try again later.'},
            status=503,
        )

    try:
        payload = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Send a valid question.'}, status=400)
    question = payload.get('question', '') if isinstance(payload, dict) else ''
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        return JsonResponse(
            {'error': 'Enter a question of 1 to 500 characters.'},
            status=400,
        )

    current_year = AcademicYear.objects.filter(is_current=True).first()
    terms = Term.objects.filter(
        academic_year=current_year
    ).order_by('start_date') if current_year else Term.objects.none()
    public_announcements = Announcement.objects.filter(
        is_published=True,
        is_public=True,
    ).order_by('-event_date', '-created_at')[:3]
    context_lines = [
        f'School: {settings.SCHOOL_NAME}',
        f'Address: {settings.SCHOOL_ADDRESS}',
        f'Location: {settings.SCHOOL_LOCATION}',
        f'Email: {settings.SCHOOL_EMAIL}',
        f'Phone: {settings.SCHOOL_PHONE}',
    ]
    if current_year:
        context_lines.append(f'Current academic year: {current_year.name}')
    for term in terms:
        if term.start_date and term.end_date:
            context_lines.append(
                f'{term.name}: {term.start_date:%d %b %Y} to {term.end_date:%d %b %Y}'
            )
    for announcement in public_announcements:
        context_lines.append(
            f'Public announcement: {announcement.title} — {announcement.message[:500]}'
        )
    try:
        answer = answer_school_question(question.strip(), '\n'.join(context_lines))
    except AIServiceError as exc:
        return JsonResponse({'error': str(exc)}, status=503)
    return JsonResponse({'answer': answer})


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
