from django.contrib import admin

from .forms import SubjectForm
from .models import (
    AcademicAuditLog, AcademicYear, Department, Enrollment, LessonPlan,
    ExaminationSession, SchoolClass, Subject, SyllabusCoverage,
    TeacherAttendance, TeachingObservation, TeachingSchedule, Term,
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


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    form = SubjectForm
    list_display = (
        'code', 'name', 'school_class_names', 'teacher', 'academic_year', 'term',
        'is_active',
    )
    list_filter = ('academic_year', 'term', 'school_classes', 'is_active', 'departments')
    search_fields = ('name', 'code', 'teacher__username', 'departments__name')
    autocomplete_fields = ('teacher', 'academic_year')
    filter_horizontal = ('departments', 'school_classes')
    list_select_related = ('teacher', 'academic_year')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'school_class', 'academic_year', 'term', 'is_active')
    list_filter = ('academic_year', 'term', 'school_class', 'is_active')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name')
    autocomplete_fields = ('student', 'school_class', 'academic_year')
    list_select_related = ('student__user', 'school_class', 'academic_year')


@admin.register(SyllabusCoverage)
class SyllabusCoverageAdmin(admin.ModelAdmin):
    list_display = (
        'academic_year', 'term', 'school_class', 'subject',
        'topics_completed', 'topics_planned', 'updated_by', 'updated_at',
    )
    list_filter = ('academic_year', 'term', 'school_class')
    search_fields = ('school_class__name', 'subject__name', 'subject__code')
    autocomplete_fields = ('academic_year', 'school_class', 'subject', 'updated_by')


@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = (
        'lesson_date', 'topic', 'teacher', 'school_class', 'subject',
        'status', 'reviewed_by',
    )
    list_filter = ('academic_year', 'term', 'status', 'school_class')
    search_fields = ('topic', 'teacher__username', 'school_class__name', 'subject__name')
    autocomplete_fields = (
        'academic_year', 'school_class', 'subject', 'teacher',
        'reviewed_by',
    )
    readonly_fields = ('reviewed_at', 'created_at', 'updated_at')


@admin.register(TeachingObservation)
class TeachingObservationAdmin(admin.ModelAdmin):
    list_display = (
        'observed_on', 'teacher', 'school_class', 'subject', 'rating',
        'lesson_prepared', 'observer',
    )
    list_filter = ('observed_on', 'rating', 'lesson_prepared', 'school_class')
    search_fields = ('teacher__username', 'observer__username', 'strengths')
    autocomplete_fields = ('teacher', 'observer', 'school_class', 'subject')


@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'teacher', 'status', 'check_in', 'check_out', 'recorded_by')
    list_filter = ('date', 'status')
    search_fields = ('teacher__username', 'teacher__first_name', 'teacher__last_name')
    autocomplete_fields = ('teacher', 'recorded_by')
    date_hierarchy = 'date'


@admin.register(AcademicAuditLog)
class AcademicAuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'object_type', 'object_id')
    list_filter = ('action', 'object_type')
    search_fields = ('summary', 'actor__username', 'object_id')
    autocomplete_fields = ('actor',)
    readonly_fields = ('actor', 'action', 'object_type', 'object_id', 'summary', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TeachingSchedule)
class TeachingScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'weekday', 'start_time', 'end_time', 'school_class', 'subject',
        'teacher', 'room', 'academic_year', 'term',
    )
    list_filter = ('academic_year', 'term', 'weekday', 'school_class')
    search_fields = ('school_class__name', 'subject__name', 'teacher__username')
    autocomplete_fields = (
        'academic_year', 'school_class', 'subject', 'teacher',
    )


@admin.register(ExaminationSession)
class ExaminationSessionAdmin(admin.ModelAdmin):
    list_display = (
        'exam_date', 'start_time', 'end_time', 'examination', 'school_class',
        'subject', 'venue',
    )
    list_filter = ('exam_date', 'examination', 'school_class')
    search_fields = (
        'examination__name', 'school_class__name', 'subject__name', 'venue',
    )
    autocomplete_fields = (
        'examination', 'school_class', 'subject', 'invigilators', 'created_by',
    )
    filter_horizontal = ('invigilators',)
