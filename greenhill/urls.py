from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from school import views as school_views

admin.site.site_header = 'Green Hill Secondary School Administration'
admin.site.site_title = 'Green Hill School Admin'
admin.site.index_title = 'School Management'

urlpatterns = [
    path('', school_views.home, name='home'),
    path('privacy/', school_views.privacy_policy, name='privacy_policy'),
    path('terms/', school_views.terms_of_service, name='terms_of_service'),
    path('cookies/', school_views.cookie_policy, name='cookie_policy'),
    path('acceptable-use/', school_views.acceptable_use, name='acceptable_use'),
    path('data-protection/', school_views.data_protection, name='data_protection'),
    path('child-protection/', school_views.child_protection, name='child_protection'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('teachers/', include('teachers.urls')),
    path('academics/', include('academics.urls')),
    path('attendance/', include('attendance.urls')),
    path('examinations/', include('examinations.urls')),
    path('finance/', include('finance.urls')),
    path('assignments/', include('assignments.urls')),
    path('communications/', include('communications.urls')),
    path('reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
