from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'is_staff',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('first_name', 'last_name', 'username')
    list_per_page = 25
    fieldsets = BaseUserAdmin.fieldsets + (
        ('School profile', {'fields': ('role', 'phone', 'address', 'photo', 'date_of_birth')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('School profile', {'fields': ('role', 'phone', 'address')}),
    )
