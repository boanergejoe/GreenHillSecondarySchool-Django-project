from django import forms

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import (
    AcademicYear, Department, Enrollment, SchoolClass, Subject, Term,
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


class SubjectForm(BootstrapFormMixin, forms.ModelForm):
    shared_codes = {'MATH', 'MAT', 'ENG', 'ENGLISH', 'ICT'}
    shared_names = {
        'mathematics', 'math', 'english', 'english language', 'ict',
        'information and communication technology',
    }

    class Meta:
        model = Subject
        fields = [
            'name', 'code', 'departments', 'school_classes', 'teacher',
            'academic_year', 'term', 'is_active', 'description',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'departments': forms.CheckboxSelectMultiple(),
            'school_classes': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['departments'].queryset = Department.objects.order_by('name')
        self.fields['teacher'].queryset = User.objects.filter(
            role=User.Role.TEACHER, is_active=True
        ).order_by('first_name', 'last_name')
        self.fields['school_classes'].queryset = SchoolClass.objects.select_related(
            'academic_year', 'department'
        ).order_by('name')

    def clean(self):
        cleaned = super().clean()
        academic_year = cleaned.get('academic_year')
        school_classes = cleaned.get('school_classes')
        if academic_year and school_classes and any(
            school_class.academic_year_id != academic_year.pk
            for school_class in school_classes
        ):
            self.add_error(
                'school_classes',
                'All classes must belong to the selected academic year.',
            )
        code = (cleaned.get('code') or '').strip().upper()
        name = (cleaned.get('name') or '').strip().lower()
        departments = cleaned.get('departments')
        if code in self.shared_codes or name in self.shared_names:
            department_codes = {
                department.code.upper() for department in departments or []
            }
            if department_codes != {'ART', 'SCI'}:
                self.add_error(
                    'departments',
                    'Mathematics, English, and ICT must be assigned to both '
                    'Arts and Science.',
                )
        if school_classes and departments:
            department_ids = {department.pk for department in departments}
            if any(
                school_class.department_id
                and school_class.department_id not in department_ids
                for school_class in school_classes
            ):
                self.add_error(
                    'departments',
                    'The selected departments must include each streamed class department.',
                )
        if academic_year and school_classes and code:
            duplicates = Subject.objects.filter(
                code__iexact=code, academic_year=academic_year,
                school_classes__in=school_classes,
            ).exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    'code',
                    'This subject code is already assigned to one or more selected classes.',
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
        if academic_year and school_class and school_class.academic_year_id != academic_year.pk:
            self.add_error('school_class', 'The class must belong to the selected academic year.')
        return cleaned
