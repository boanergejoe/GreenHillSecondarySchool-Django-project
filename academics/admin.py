from django.contrib import admin

from .models import (
    AcademicYear, Course, Department, Enrollment, SchoolClass, Semester, Subject,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'start_date', 'end_date', 'is_current')
    list_filter = ('academic_year',)


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'academic_year', 'class_teacher', 'capacity')
    list_filter = ('academic_year', 'department')
    search_fields = ('name', 'level')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department', 'credit_units', 'is_active')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'school_class', 'teacher', 'academic_year', 'is_active')
    list_filter = ('academic_year', 'school_class', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'school_class', 'academic_year', 'semester', 'is_active')
    list_filter = ('academic_year', 'school_class', 'is_active')
