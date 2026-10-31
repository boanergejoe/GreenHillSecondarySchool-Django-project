from django import forms

from academics.models import AcademicYear, SchoolClass, Semester, Subject
from accounts.forms import BootstrapFormMixin

from .models import Examination, Result


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class ExaminationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Examination
        fields = [
            'name', 'exam_type', 'academic_year', 'semester', 'school_class',
            'start_date', 'end_date', 'total_marks', 'is_published',
        ]
        widgets = {'start_date': DATE_WIDGET, 'end_date': DATE_WIDGET}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End date cannot be before the start date.')
        return cleaned


class ResultForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Result
        fields = ['student', 'examination', 'subject', 'marks_obtained', 'total_marks', 'remarks']


class ResultFilterForm(BootstrapFormMixin, forms.Form):
    examination = forms.ModelChoiceField(
        queryset=Examination.objects.select_related('academic_year'),
        required=False,
    )
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(), required=False
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.select_related('school_class'), required=False
    )
