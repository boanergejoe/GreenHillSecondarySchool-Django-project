from django.contrib import admin

from academics.models import Enrollment

from .models import Parent, Student


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    autocomplete_fields = ('school_class', 'academic_year')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id', 'user', 'school_class', 'department', 'gender', 'status',
        'admission_date', 'is_archived',
    )
    list_filter = ('is_archived', 'status', 'gender', 'school_class', 'department')
    search_fields = (
        'student_id', 'user__first_name', 'user__last_name', 'user__email',
        'department__name',
    )
    autocomplete_fields = ('user', 'school_class', 'department', 'parent')
    list_select_related = ('user', 'school_class', 'department', 'parent')
    date_hierarchy = 'admission_date'
    list_per_page = 25
    inlines = [EnrollmentInline]
    actions = ('archive_selected_students', 'restore_selected_students')

    @admin.action(description='Archive selected students')
    def archive_selected_students(self, request, queryset):
        from .services import archive_student

        count = 0
        for student in queryset:
            archive_student(student, request.user)
            count += 1
        self.message_user(request, f'{count} student record(s) archived.')

    @admin.action(description='Restore selected students')
    def restore_selected_students(self, request, queryset):
        from .services import restore_student

        count = 0
        for student in queryset:
            restore_student(student)
            count += 1
        self.message_user(request, f'{count} student record(s) restored.')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'relationship', 'occupation', 'alternate_phone')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    list_per_page = 25
