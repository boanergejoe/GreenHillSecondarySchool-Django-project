from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import (
    AcademicYear, Course, Department, Enrollment, SchoolClass, Subject, Term,
)


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})


class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class AcademicYearForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {'start_date': DATE_WIDGET, 'end_date': DATE_WIDGET}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError('End date must be after the start date.')
        return cleaned


class TermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Term
        fields = ['name', 'academic_year', 'start_date', 'end_date', 'is_current']
        widgets = {'start_date': DATE_WIDGET, 'end_date': DATE_WIDGET}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end <= start:
            raise forms.ValidationError('End date must be after the start date.')
        return cleaned


class SchoolClassForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = [
            'name', 'level', 'stream', 'department', 'academic_year',
            'class_teacher', 'capacity', 'room',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['class_teacher'].queryset = User.objects.filter(
            role=User.Role.TEACHER, is_active=True
        ).order_by('first_name', 'last_name')


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            'name', 'code', 'department', 'credit_units', 'is_active', 'description',
        ]
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class SubjectForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subject
        fields = [
            'name', 'code', 'course', 'departments', 'school_class', 'teacher',
            'academic_year', 'term', 'is_active', 'description',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'departments': forms.SelectMultiple(attrs={'size': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['departments'].queryset = Department.objects.order_by('name')
        self.fields['teacher'].queryset = User.objects.filter(
            role=User.Role.TEACHER, is_active=True
        ).order_by('first_name', 'last_name')
        self.fields['school_class'].queryset = SchoolClass.objects.select_related(
            'academic_year'
        ).order_by('name')
        self.fields['term'].queryset = Term.objects.select_related(
            'academic_year'
        ).order_by('-academic_year__start_date', 'name')

    def clean(self):
        cleaned = super().clean()
        academic_year = cleaned.get('academic_year')
        school_class = cleaned.get('school_class')
        term = cleaned.get('term')
        if academic_year and school_class and school_class.academic_year_id != academic_year.pk:
            self.add_error('school_class', 'The class must belong to the selected academic year.')
        if academic_year and term and term.academic_year_id != academic_year.pk:
            self.add_error('term', 'The term must belong to the selected academic year.')
        departments = cleaned.get('departments')
        if school_class and school_class.department_id and departments:
            if not departments.filter(pk=school_class.department_id).exists():
                self.add_error(
                    'departments',
                    'Streamed classes must offer at least one subject from their department.',
                )
        return cleaned


class EnrollmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = [
            'student', 'school_class', 'academic_year', 'term', 'enrolled_on',
            'is_active',
        ]
        widgets = {'enrolled_on': DATE_WIDGET}

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
