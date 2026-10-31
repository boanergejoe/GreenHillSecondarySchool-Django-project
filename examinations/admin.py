from django.contrib import admin

from .models import Examination, Result


class ResultInline(admin.TabularInline):
    model = Result
    extra = 0


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'academic_year', 'term', 'school_class', 'start_date', 'end_date', 'is_published')
    list_filter = ('exam_type', 'academic_year', 'term', 'school_class', 'is_published')
    search_fields = ('name', 'school_class__name')
    autocomplete_fields = ('academic_year', 'term', 'school_class')
    list_select_related = ('academic_year', 'term', 'school_class')
    date_hierarchy = 'start_date'
    inlines = [ResultInline]


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'examination', 'subject', 'marks_obtained', 'grade')
    list_filter = ('examination', 'subject', 'grade')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ('student', 'examination', 'subject', 'entered_by')
    list_select_related = ('student__user', 'examination', 'subject', 'entered_by')
    list_per_page = 25
