from django.urls import path

from . import views

app_name = 'assignments'

urlpatterns = [
    path('', views.AssignmentListView.as_view(), name='list'),
    path('add/', views.AssignmentCreateView.as_view(), name='create'),
    path('<int:pk>/', views.assignment_detail, name='detail'),
    path('<int:pk>/edit/', views.AssignmentUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.AssignmentDeleteView.as_view(), name='delete'),
    path('<int:pk>/submit/', views.submit_assignment, name='submit'),
    path('submissions/<int:pk>/review/', views.review_submission, name='review'),
]
