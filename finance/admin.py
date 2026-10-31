from django.contrib import admin

from .models import Fee, Payment


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'school_class', 'academic_year', 'amount', 'due_date', 'is_active')
    list_filter = ('academic_year', 'school_class', 'is_active')
    search_fields = ('name',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'fee', 'amount', 'method', 'payment_date', 'recorded_by')
    list_filter = ('method', 'payment_date')
    search_fields = ('receipt_number', 'student__student_id', 'student__user__first_name', 'reference')
    readonly_fields = ('receipt_number',)
