from django import forms

from academics.models import AcademicYear, SchoolClass, Subject
from accounts.forms import BootstrapFormMixin

from .models import Examination, Result


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class SchoolClassChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name} ({obj.academic_year.name})'


class ExaminationForm(BootstrapFormMixin, forms.ModelForm):
    school_classes = SchoolClassChoiceField(
        queryset=SchoolClass.objects.select_related('academic_year'),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        help_text='Select the classes sitting this examination. Leave blank for all classes.',
    )

    class Meta:
        model = Examination
        fields = [
            'name', 'exam_type', 'academic_year', 'term', 'school_classes',
            'start_date', 'end_date', 'total_marks', 'is_published',
        ]
        widgets = {
            'term': forms.RadioSelect(),
            'start_date': DATE_WIDGET,
            'end_date': DATE_WIDGET,
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        academic_year = cleaned.get('academic_year')
        if start and end and end < start:
            raise forms.ValidationError('End date cannot be before the start date.')
        school_classes = cleaned.get('school_classes')
        if academic_year and school_classes:
            invalid_classes = [
                school_class for school_class in school_classes
                if school_class.academic_year_id != academic_year.pk
            ]
            if invalid_classes:
                self.add_error(
                    'school_classes',
                    'All selected classes must belong to the selected academic year.',
                )
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
        queryset=Subject.objects.prefetch_related('school_classes'), required=False
    )
