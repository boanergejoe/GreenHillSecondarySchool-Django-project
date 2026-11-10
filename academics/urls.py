from django.urls import path

from . import views

app_name = 'academics'

urlpatterns = [
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/add/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),

    path('years/', views.AcademicYearListView.as_view(), name='year_list'),
    path('years/add/', views.AcademicYearCreateView.as_view(), name='year_create'),
    path('years/<int:pk>/edit/', views.AcademicYearUpdateView.as_view(), name='year_update'),
    path('years/<int:pk>/delete/', views.AcademicYearDeleteView.as_view(), name='year_delete'),

    path('terms/', views.TermListView.as_view(), name='term_list'),
    path('terms/add/', views.TermCreateView.as_view(), name='term_create'),
    path('terms/<int:pk>/edit/', views.TermUpdateView.as_view(), name='term_update'),
    path('terms/<int:pk>/delete/', views.TermDeleteView.as_view(), name='term_delete'),

    path('classes/', views.SchoolClassListView.as_view(), name='class_list'),
    path('classes/add/', views.SchoolClassCreateView.as_view(), name='class_create'),
    path('classes/<int:pk>/edit/', views.SchoolClassUpdateView.as_view(), name='class_update'),
    path('classes/<int:pk>/delete/', views.SchoolClassDeleteView.as_view(), name='class_delete'),

    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', views.SubjectCreateView.as_view(), name='subject_create'),
    path('subjects/<int:pk>/edit/', views.SubjectUpdateView.as_view(), name='subject_update'),
    path('subjects/<int:pk>/delete/', views.SubjectDeleteView.as_view(), name='subject_delete'),

    path('enrollments/', views.EnrollmentListView.as_view(), name='enrollment_list'),
    path('enrollments/add/', views.EnrollmentCreateView.as_view(), name='enrollment_create'),
    path('enrollments/<int:pk>/edit/', views.EnrollmentUpdateView.as_view(), name='enrollment_update'),
    path('enrollments/<int:pk>/delete/', views.EnrollmentDeleteView.as_view(), name='enrollment_delete'),

    path('syllabus/', views.SyllabusCoverageListView.as_view(), name='syllabus_coverage_list'),
    path('syllabus/add/', views.SyllabusCoverageCreateView.as_view(), name='syllabus_coverage_create'),
    path('syllabus/<int:pk>/edit/', views.SyllabusCoverageUpdateView.as_view(), name='syllabus_coverage_update'),
    path('syllabus/<int:pk>/delete/', views.SyllabusCoverageDeleteView.as_view(), name='syllabus_coverage_delete'),

    path('lesson-plans/', views.LessonPlanListView.as_view(), name='lesson_plan_list'),
    path('lesson-plans/add/', views.LessonPlanCreateView.as_view(), name='lesson_plan_create'),
    path('lesson-plans/<int:pk>/edit/', views.LessonPlanUpdateView.as_view(), name='lesson_plan_update'),
    path('lesson-plans/<int:pk>/review/', views.LessonPlanReviewView.as_view(), name='lesson_plan_review'),

    path('observations/', views.TeachingObservationListView.as_view(), name='observation_list'),
    path('observations/add/', views.TeachingObservationCreateView.as_view(), name='observation_create'),
    path('teacher-attendance/', views.TeacherAttendanceListView.as_view(), name='teacher_attendance_list'),
    path('teacher-attendance/add/', views.TeacherAttendanceCreateView.as_view(), name='teacher_attendance_create'),
    path('teacher-attendance/<int:pk>/edit/', views.TeacherAttendanceUpdateView.as_view(), name='teacher_attendance_update'),
    path('teacher-attendance/<int:pk>/delete/', views.TeacherAttendanceDeleteView.as_view(), name='teacher_attendance_delete'),
    path('activity/', views.AcademicAuditLogListView.as_view(), name='academic_activity'),
    path('notices/add/', views.AcademicNoticeCreateView.as_view(), name='academic_notice_create'),

    path('teaching-schedule/', views.TeachingScheduleListView.as_view(), name='teaching_schedule_list'),
    path('teaching-schedule/add/', views.TeachingScheduleCreateView.as_view(), name='teaching_schedule_create'),
    path('teaching-schedule/<int:pk>/edit/', views.TeachingScheduleUpdateView.as_view(), name='teaching_schedule_update'),
    path('teaching-schedule/<int:pk>/delete/', views.TeachingScheduleDeleteView.as_view(), name='teaching_schedule_delete'),

    path('examination-timetable/', views.ExaminationSessionListView.as_view(), name='examination_session_list'),
    path('examination-timetable/add/', views.ExaminationSessionCreateView.as_view(), name='examination_session_create'),
    path('examination-timetable/<int:pk>/edit/', views.ExaminationSessionUpdateView.as_view(), name='examination_session_update'),
    path('examination-timetable/<int:pk>/delete/', views.ExaminationSessionDeleteView.as_view(), name='examination_session_delete'),
]
