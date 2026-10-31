from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('fees/', views.FeeListView.as_view(), name='fee_list'),
    path('fees/add/', views.FeeCreateView.as_view(), name='fee_create'),
    path('fees/<int:pk>/edit/', views.FeeUpdateView.as_view(), name='fee_update'),
    path('fees/<int:pk>/delete/', views.FeeDeleteView.as_view(), name='fee_delete'),

    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/add/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:pk>/edit/', views.PaymentUpdateView.as_view(), name='payment_update'),
    path('payments/<int:pk>/delete/', views.PaymentDeleteView.as_view(), name='payment_delete'),
    path('payments/<int:pk>/receipt/', views.receipt_pdf, name='receipt_pdf'),

    path('statement/<int:student_id>/', views.fee_statement, name='fee_statement'),
    path('overview/', views.financial_overview, name='financial_overview'),
]
