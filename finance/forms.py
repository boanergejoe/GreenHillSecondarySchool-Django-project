from django import forms

from academics.models import AcademicYear, SchoolClass
from accounts.forms import BootstrapFormMixin
from students.models import Student

from .models import Fee, Payment


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class FeeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Fee
        fields = [
            'name', 'school_class', 'academic_year', 'term', 'amount',
            'due_date', 'is_active', 'description',
        ]
        widgets = {
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
        term = cleaned.get('term')
        if academic_year and school_class and school_class.academic_year_id != academic_year.pk:
            self.add_error('school_class', 'The class must belong to the selected academic year.')
        if academic_year and term and term.academic_year_id != academic_year.pk:
            self.add_error('term', 'The term must belong to the selected academic year.')
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
        ).order_by('user__first_name', 'user__last_name')
        self.fields['fee'].queryset = Fee.objects.select_related(
            'school_class', 'academic_year'
        ).order_by('-academic_year__start_date', 'name')


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
