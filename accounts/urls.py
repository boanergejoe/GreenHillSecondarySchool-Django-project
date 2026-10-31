from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.SchoolLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html',
        success_url='/accounts/profile/',
    ), name='password_change'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('staff/', views.StaffListView.as_view(), name='user_list'),
    path('staff/add/', views.StaffCreateView.as_view(), name='user_create'),
    path('staff/<int:pk>/edit/', views.StaffUpdateView.as_view(), name='user_update'),
    path('staff/<int:pk>/delete/', views.StaffDeleteView.as_view(), name='user_delete'),
]
