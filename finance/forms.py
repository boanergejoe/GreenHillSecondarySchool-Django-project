from decimal import Decimal

from django import forms
from django.db.models import Q, Sum

from academics.models import AcademicYear, SchoolClass
from accounts.forms import BootstrapFormMixin
from students.models import Student

from .models import Fee, Payment
from .services import active_fees_for_student


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class FeeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Fee
        fields = [
            'name', 'school_class', 'academic_year', 'term', 'amount',
            'due_date', 'is_active', 'description',
        ]
        widgets = {
            'term': forms.RadioSelect(),
            'due_date': DATE_WIDGET,
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school_class'].required = False
        self.fields['school_class'].empty_label = 'All classes'
        self.fields['school_class'].help_text = (
            'Leave blank to apply this fee to every student in every class.'
        )

    def clean(self):
        cleaned = super().clean()
        academic_year = cleaned.get('academic_year')
        school_class = cleaned.get('school_class')
        if academic_year and school_class and school_class.academic_year_id != academic_year.pk:
            self.add_error('school_class', 'The class must belong to the selected academic year.')
        return cleaned


class PaymentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'student', 'fee', 'amount', 'payment_date', 'method', 'reference', 'remarks',
        ]
        widgets = {'payment_date': DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.select_related(
            'user', 'school_class'
        ).filter(is_archived=False).order_by('user__first_name', 'user__last_name')
        self.fields['fee'].required = True
        self.fields['amount'].min_value = Decimal('0.01')
        fee_queryset = Fee.objects.select_related(
            'school_class', 'academic_year'
        )
        selected_student_id = (
            self.data.get('student') if self.is_bound
            else self.initial.get('student', self.instance.student_id)
        )
        selected_student = self.fields['student'].queryset.filter(
            pk=selected_student_id
        ).first() if selected_student_id else None
        if selected_student:
            fee_queryset = active_fees_for_student(selected_student)
            if self.instance.pk and self.instance.fee_id:
                fee_queryset = Fee.objects.filter(
                    Q(pk__in=fee_queryset) | Q(pk=self.instance.fee_id)
                ).select_related('school_class', 'academic_year')
        else:
            fee_queryset = fee_queryset.filter(is_active=True)
        self.fields['fee'].queryset = fee_queryset.order_by(
            '-academic_year__start_date', 'name'
        )

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get('student')
        fee = cleaned.get('fee')
        amount = cleaned.get('amount')
        if not student or not fee:
            return cleaned

        same_existing_payment = (
            self.instance.pk
            and self.instance.student_id == student.pk
            and self.instance.fee_id == fee.pk
        )
        if not same_existing_payment and not active_fees_for_student(student).filter(
            pk=fee.pk
        ).exists():
            self.add_error(
                'fee',
                'Select an active fee that applies to this student’s class and academic year.',
            )
            return cleaned

        payments = Payment.objects.filter(student=student, fee=fee)
        if self.instance.pk:
            payments = payments.exclude(pk=self.instance.pk)
        paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        balance = max(fee.amount - paid, Decimal('0'))
        if amount is not None and amount > balance:
            self.add_error(
                'amount',
                f'The payment cannot exceed the remaining fee balance of {balance:,.2f}.',
            )
        return cleaned


class PaymentFilterForm(BootstrapFormMixin, forms.Form):
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(), required=False
    )
    method = forms.ChoiceField(
        choices=[('', 'All methods')] + list(Payment.Method.choices), required=False
    )
    start_date = forms.DateField(required=False, widget=DATE_WIDGET)
    end_date = forms.DateField(required=False, widget=DATE_WIDGET)


class FeeFilterForm(BootstrapFormMixin, forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(), required=False
    )
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(), required=False
    )
