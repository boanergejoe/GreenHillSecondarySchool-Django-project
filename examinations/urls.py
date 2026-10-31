from django.urls import path

from . import views

app_name = 'examinations'

urlpatterns = [
    path('', views.ExaminationListView.as_view(), name='exam_list'),
    path('add/', views.ExaminationCreateView.as_view(), name='exam_create'),
    path('<int:pk>/', views.exam_detail, name='exam_detail'),
    path('<int:pk>/edit/', views.ExaminationUpdateView.as_view(), name='exam_update'),
    path('<int:pk>/delete/', views.ExaminationDeleteView.as_view(), name='exam_delete'),
    path('<int:pk>/enter-results/', views.enter_results, name='enter_results'),
    path('results/', views.result_list, name='result_list'),
    path('results/<int:pk>/delete/', views.ResultDeleteView.as_view(), name='result_delete'),
    path('report-card/<int:student_id>/<int:exam_id>/', views.report_card, name='report_card'),
    path('report-card/<int:student_id>/<int:exam_id>/pdf/', views.report_card_pdf, name='report_card_pdf'),
]
