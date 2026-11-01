from django import forms
from django.db import transaction

from accounts.forms import BootstrapFormMixin
from accounts.models import User

from .models import (
    AcademicYear, Department, Enrollment, SchoolClass, Subject, Term,
)


DATE_WIDGET = forms.DateInput(attrs={'type': 'date'})
TERM_DATE_FIELDS = (
    (Term.Name.TERM_1, 'term_1_start_date', 'term_1_end_date'),
    (Term.Name.TERM_2, 'term_2_start_date', 'term_2_end_date'),
    (Term.Name.TERM_3, 'term_3_start_date', 'term_3_end_date'),
)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for term_name, start_field, end_field in TERM_DATE_FIELDS:
            label = term_name
            self.fields[start_field] = forms.DateField(
                label=f'{label} start date',
                required=False,
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                help_text='Leave both dates blank to leave this term unchanged.',
            )
            self.fields[end_field] = forms.DateField(
                label=f'{label} end date',
                required=False,
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            )

        existing_terms = {}
        if self.instance.pk:
            existing_terms = {
                term.name: term
                for term in Term.objects.filter(academic_year=self.instance)
            }
        for term_name, start_field, end_field in TERM_DATE_FIELDS:
            term = existing_terms.get(term_name)
            if term:
                self.initial[start_field] = term.start_date
                self.initial[end_field] = term.end_date

        self.order_fields([
            'name', 'start_date', 'end_date',
            *(field for _, start, end in TERM_DATE_FIELDS for field in (start, end)),
            'is_current',
        ])

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'End date must be after the start date.')

        term_ranges = []
        for _, start_field, end_field in TERM_DATE_FIELDS:
            term_start = cleaned.get(start_field)
            term_end = cleaned.get(end_field)
            if bool(term_start) != bool(term_end):
                missing_field = end_field if term_start else start_field
                self.add_error(
                    missing_field,
                    'Enter both the start and end dates for this term.',
                )
                continue
            if not term_start:
                continue
            if term_end <= term_start:
                self.add_error(end_field, 'End date must be after the start date.')
                continue
            if start and term_start < start:
                self.add_error(
                    start_field,
                    'Term start date must fall within the academic year.',
                )
            if end and term_end > end:
                self.add_error(
                    end_field,
                    'Term end date must fall within the academic year.',
                )
            term_ranges.append((term_start, term_end, start_field))

        term_ranges.sort()
        for previous, current in zip(term_ranges, term_ranges[1:]):
            if current[0] <= previous[1]:
                self.add_error(
                    current[2],
                    'Term date ranges must not overlap.',
                )
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        academic_year = super().save(commit=False)
        if commit:
            academic_year.save()
            self.save_m2m()
            for term_name, start_field, end_field in TERM_DATE_FIELDS:
                start_date = self.cleaned_data.get(start_field)
                end_date = self.cleaned_data.get(end_field)
                if start_date and end_date:
                    Term.objects.update_or_create(
                        academic_year=academic_year,
                        name=term_name,
                        defaults={
                            'start_date': start_date,
                            'end_date': end_date,
                        },
                    )
        return academic_year


class TermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Term
        fields = ['name', 'academic_year', 'start_date', 'end_date', 'is_current']
        widgets = {
            'name': forms.RadioSelect(),
            'start_date': DATE_WIDGET,
            'end_date': DATE_WIDGET,
        }

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
            'term': forms.RadioSelect(),
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
        widgets = {
            'term': forms.RadioSelect(),
            'enrolled_on': DATE_WIDGET,
        }

    def clean(self):
        cleaned = super().clean()
        academic_year = cleaned.get('academic_year')
        school_class = cleaned.get('school_class')
        if academic_year and school_class and school_class.academic_year_id != academic_year.pk:
            self.add_error('school_class', 'The class must belong to the selected academic year.')
        return cleaned
