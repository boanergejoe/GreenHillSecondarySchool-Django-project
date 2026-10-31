from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'school_class', 'subject', 'date', 'status', 'recorded_by')
    list_filter = ('status', 'date', 'school_class')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ('student', 'school_class', 'subject', 'recorded_by')
    list_select_related = ('student__user', 'school_class', 'subject', 'recorded_by')
    date_hierarchy = 'date'
    list_per_page = 25
