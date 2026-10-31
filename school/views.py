from django.shortcuts import render


def home(request):
    return render(request, 'landing/home.html')


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
