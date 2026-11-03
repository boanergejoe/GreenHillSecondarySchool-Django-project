from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    path('', views.StudentListView.as_view(), name='student_list'),
    path('add/', views.StudentCreateView.as_view(), name='student_create'),
    path('promote/', views.promote_students, name='student_promote'),
    path('archived/', views.ArchivedStudentListView.as_view(), name='archived_students'),
    path('archived/<int:pk>/restore/', views.restore_archived_student, name='student_restore'),
    path('readmission/request/', views.request_readmission, name='readmission_request'),
    path('readmission/requests/', views.readmission_request_list, name='readmission_request_list'),
    path(
        'readmission/requests/<int:pk>/review/',
        views.review_readmission_request,
        name='readmission_request_review',
    ),
    path('<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('<int:pk>/readmit/', views.readmit_student, name='student_readmit'),
    path('<int:pk>/edit/', views.StudentUpdateView.as_view(), name='student_update'),
    path('<int:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    path('parents/', views.ParentListView.as_view(), name='parent_list'),
    path('parents/add/', views.ParentCreateView.as_view(), name='parent_create'),
    path('parents/<int:pk>/', views.ParentDetailView.as_view(), name='parent_detail'),
    path('parents/<int:pk>/edit/', views.ParentUpdateView.as_view(), name='parent_update'),
    path('parents/<int:pk>/delete/', views.ParentDeleteView.as_view(), name='parent_delete'),
]
