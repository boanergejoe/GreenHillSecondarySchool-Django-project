from django.contrib import admin

from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        'staff_id', 'user', 'department', 'assigned_class_names', 'specialization',
        'employment_type', 'status',
    )
    list_filter = ('status', 'employment_type', 'department')
    search_fields = ('staff_id', 'user__first_name', 'user__last_name', 'specialization')
    autocomplete_fields = ('user', 'department')
    filter_horizontal = ('assigned_classes',)
    list_select_related = ('user', 'department')
    date_hierarchy = 'date_joined'
    list_per_page = 25
