from django.urls import path

from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceListView.as_view(), name='list'),
    path('record/', views.take_attendance, name='take'),
    path('report/', views.attendance_report, name='report'),
]
