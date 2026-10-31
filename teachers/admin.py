from django.contrib import admin

from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'department', 'specialization', 'employment_type', 'status')
    list_filter = ('status', 'employment_type', 'department')
    search_fields = ('staff_id', 'user__first_name', 'user__last_name', 'specialization')
