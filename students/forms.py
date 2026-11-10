from django import forms
from django.db import transaction
from django.utils import timezone

from accounts.forms import BootstrapFormMixin, UserAccountFormMixin
from accounts.models import User
from academics.models import AcademicYear, Department, Enrollment, SchoolClass, Term

from .models import Parent, ReadmissionRequest, Student


class SchoolClassSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        school_class = getattr(value, 'instance', None)
        if school_class:
            option['attrs']['data-level'] = school_class.level
        return option


class ParentForm(UserAccountFormMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Parent
        fields = [
            'occupation', 'relationship', 'address', 'alternate_phone', 'national_id',
        ]

    def save(self, commit=True):
        user = self.save_user(User.Role.PARENT, commit=commit)
        parent = super().save(commit=False)
        parent.user = user
        if commit:
            parent.save()
            self.save_m2m()
        return parent


class StudentForm(UserAccountFormMixin, BootstrapFormMixin, forms.ModelForm):
    term = forms.MultipleChoiceField(
        choices=Term.Name.choices,
        widget=forms.CheckboxSelectMultiple(),
        help_text='Select one or more terms for this student enrollment.',
    )

    class Meta:
        model = Student
        fields = [
            'student_id', 'school_class', 'department', 'parent', 'admission_date',
            'date_of_birth', 'gender', 'status', 'address', 'guardian_name',
            'guardian_phone', 'blood_group', 'medical_notes',
        ]
        widgets = {
            'school_class': SchoolClassSelect(),
            'admission_date': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'medical_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and self.user.role == User.Role.REGISTRAR:
            self.fields.pop('blood_group')
            self.fields.pop('medical_notes')
        self.fields['student_id'].help_text = 'Leave blank to generate automatically.'
        self.fields['parent'].queryset = Parent.objects.select_related('user')
        self.fields['department'].required = False
        self.fields['department'].help_text = (
            'Senior 1 and Senior 2 are neutral and do not use departments. '
            'Select a department for Senior 3 and Senior 4.'
        )
        if 'blood_group' in self.fields:
            self.fields['blood_group'].help_text = (
                'Collected for emergency care; only administrators and accountants can view it.'
            )
            self.fields['medical_notes'].help_text = (
                'Record only health information needed for student safety. Access is limited '
                'to administrators and accountants.'
            )
        self.fields['school_class'].queryset = SchoolClass.objects.select_related(
            'academic_year'
        ).order_by('name')
        self.fields['date_of_birth'].widget.attrs['max'] = (
            timezone.localdate().isoformat()
        )
        self.fields['department'].queryset = Department.objects.order_by('name')
        enrollment_terms = []
        if self.instance.pk and self.instance.school_class_id:
            enrollment_terms = list(Enrollment.objects.filter(
                student=self.instance,
                school_class_id=self.instance.school_class_id,
                academic_year_id=self.instance.school_class.academic_year_id,
                is_active=True,
            ).values_list('term', flat=True))
        school_class_id = (
            self.data.get('school_class') if self.is_bound
            else self.initial.get('school_class', self.instance.school_class_id)
        )
        school_class = None
        if school_class_id:
            try:
                school_class_pk = self.fields['school_class'].to_python(school_class_id)
            except forms.ValidationError:
                school_class_pk = None
            if school_class_pk:
                school_class = self.fields['school_class'].queryset.filter(
                    pk=school_class_pk.pk
                ).first()
        terms = Term.objects.filter(is_current=True)
        if school_class:
            terms = terms.filter(academic_year_id=school_class.academic_year_id)
        current_term = terms.order_by(
            '-academic_year__start_date', 'name'
        ).first()
        if enrollment_terms:
            self.fields['term'].initial = enrollment_terms
        elif current_term:
            self.fields['term'].initial = [current_term.name]

    @transaction.atomic
    def save(self, commit=True):
        user = self.save_user(User.Role.STUDENT, commit=commit)
        student = super().save(commit=False)
        student.user = user
        if commit:
            student.save()
            school_class = student.school_class
            terms = self.cleaned_data['term']
            active = student.status == Student.Status.ACTIVE
            if school_class:
                Enrollment.objects.filter(
                    student=student,
                    school_class=school_class,
                    academic_year=school_class.academic_year,
                ).exclude(term__in=terms).update(is_active=False)
                for term in terms:
                    Enrollment.objects.update_or_create(
                        student=student,
                        school_class=school_class,
                        academic_year=school_class.academic_year,
                        term=term,
                        defaults={
                            'enrolled_on': student.admission_date,
                            'is_active': active,
                        },
                    )
        return student

    def clean(self):
        cleaned = super().clean()
        date_of_birth = cleaned.get('date_of_birth')
        if date_of_birth and date_of_birth > timezone.localdate():
            self.add_error(
                'date_of_birth', 'Date of birth cannot be in the future.'
            )
        school_class = cleaned.get('school_class')
        department = cleaned.get('department')
        if school_class and school_class.level in (
            SchoolClass.Level.SENIOR_3, SchoolClass.Level.SENIOR_4
        ):
            if not department:
                self.add_error('department', 'Select the student department for this class.')
            elif school_class.department_id != department.pk:
                self.add_error(
                    'department',
                    'The department must match the selected class.',
                )
        elif school_class:
            cleaned['department'] = None
        return cleaned


class ReadmissionForm(BootstrapFormMixin, forms.Form):
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.select_related('academic_year').order_by(
            '-academic_year__start_date', 'name'
        ),
    )
    terms = forms.MultipleChoiceField(
        choices=Term.Name.choices,
        widget=forms.CheckboxSelectMultiple(),
    )
    admission_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def clean(self):
        cleaned = super().clean()
        school_class = cleaned.get('school_class')
        terms = cleaned.get('terms')
        if school_class and not terms:
            self.add_error('terms', 'Select at least one term for re-admission.')
        return cleaned


class StudentReadmissionRequestForm(BootstrapFormMixin, forms.ModelForm):
    terms = forms.MultipleChoiceField(
        choices=Term.Name.choices,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = ReadmissionRequest
        fields = ['school_class', 'terms', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = AcademicYear.objects.filter(is_current=True).first()
        classes = SchoolClass.objects.select_related(
            'academic_year'
        ).order_by('name')
        self.fields['school_class'].queryset = (
            classes.filter(academic_year=current_year)
            if current_year else classes.none()
        )
        self.fields['message'].required = False

    def clean_terms(self):
        terms = self.cleaned_data['terms']
        if not terms:
            raise forms.ValidationError('Select at least one term.')
        return terms

    def save(self, commit=True):
        request = super().save(commit=False)
        request.terms = self.cleaned_data['terms']
        if commit:
            request.save()
        return request
