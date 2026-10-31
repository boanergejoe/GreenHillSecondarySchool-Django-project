from django.contrib import admin

from .models import Fee, Payment


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'school_class', 'academic_year', 'term', 'amount', 'due_date', 'is_active')
    list_filter = ('academic_year', 'term', 'school_class', 'is_active')
    search_fields = ('name', 'school_class__name')
    autocomplete_fields = ('school_class', 'academic_year')
    list_select_related = ('school_class', 'academic_year')
    date_hierarchy = 'due_date'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'fee', 'amount', 'method', 'payment_date', 'recorded_by')
    list_filter = ('method', 'payment_date')
    search_fields = ('receipt_number', 'student__student_id', 'student__user__first_name', 'reference')
    autocomplete_fields = ('student', 'fee', 'recorded_by')
    list_select_related = ('student__user', 'fee', 'recorded_by')
    readonly_fields = ('receipt_number',)
    date_hierarchy = 'payment_date'
    list_per_page = 25
