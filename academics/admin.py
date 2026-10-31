from django.contrib import admin

from .models import (
    AcademicYear, Course, Department, Enrollment, SchoolClass, Subject, Term,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('name',)
    date_hierarchy = 'start_date'
    ordering = ('-start_date',)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'start_date', 'end_date', 'is_current')
    list_filter = ('academic_year', 'is_current', 'name')
    search_fields = ('name', 'academic_year__name')
    autocomplete_fields = ('academic_year',)
    date_hierarchy = 'start_date'


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'stream', 'department', 'academic_year', 'class_teacher', 'capacity')
    list_filter = ('academic_year', 'level', 'stream', 'department')
    search_fields = ('name', 'level', 'stream', 'class_teacher__username')
    autocomplete_fields = ('department', 'academic_year', 'class_teacher')
    list_select_related = ('department', 'academic_year', 'class_teacher')
    ordering = ('academic_year', 'level', 'name')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'credit_units', 'is_active')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'code')
    autocomplete_fields = ('department',)
    list_select_related = ('department',)
    ordering = ('code',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'school_class', 'teacher', 'academic_year', 'term', 'is_active')
    list_filter = ('academic_year', 'term', 'school_class', 'is_active')
    search_fields = ('name', 'code', 'teacher__username')
    autocomplete_fields = ('course', 'school_class', 'teacher', 'academic_year', 'term')
    filter_horizontal = ('departments',)
    list_select_related = ('course', 'school_class', 'teacher', 'academic_year', 'term')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'school_class', 'academic_year', 'term', 'is_active')
    list_filter = ('academic_year', 'term', 'school_class', 'is_active')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ('student', 'school_class', 'academic_year', 'term')
    list_select_related = ('student__user', 'school_class', 'academic_year', 'term')
