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
