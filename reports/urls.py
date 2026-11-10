from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='index'),
    path('students/<str:fmt>/', views.export_students, name='export_students'),
    path('teachers/<str:fmt>/', views.export_teachers, name='export_teachers'),
    path('attendance/<str:fmt>/', views.export_attendance, name='export_attendance'),
    path('results/<str:fmt>/', views.export_results, name='export_results'),
    path('finance/<str:fmt>/', views.export_finance, name='export_finance'),
    path('class-performance/', views.class_performance, name='class_performance'),
    path('teacher-performance/', views.teacher_performance, name='teacher_performance'),
    path('subject-performance/', views.subject_performance, name='subject_performance'),
    path('department-performance/', views.department_performance, name='department_performance'),
    path('syllabus-coverage/', views.syllabus_coverage_report, name='syllabus_coverage'),
    path('student-progress/', views.student_progress, name='student_progress'),
]
