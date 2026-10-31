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
        'admission_date',
    )
    list_filter = ('status', 'gender', 'school_class', 'department')
    search_fields = (
        'student_id', 'user__first_name', 'user__last_name', 'user__email',
        'department__name',
    )
    autocomplete_fields = ('user', 'school_class', 'department', 'parent')
    list_select_related = ('user', 'school_class', 'department', 'parent')
    date_hierarchy = 'admission_date'
    list_per_page = 25
    inlines = [EnrollmentInline]


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'relationship', 'occupation', 'alternate_phone')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    list_per_page = 25
