from django.contrib import admin

from .models import Parent, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'school_class', 'gender', 'status', 'admission_date')
    list_filter = ('status', 'gender', 'school_class')
    search_fields = ('student_id', 'user__first_name', 'user__last_name', 'user__email')
    autocomplete_fields = ('user', 'school_class', 'parent')
    list_select_related = ('user', 'school_class', 'parent')
    date_hierarchy = 'admission_date'
    list_per_page = 25


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'relationship', 'occupation', 'alternate_phone')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    list_per_page = 25
