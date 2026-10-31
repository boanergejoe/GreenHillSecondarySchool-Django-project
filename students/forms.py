from django import forms
from django.db import transaction

from accounts.forms import BootstrapFormMixin, UserAccountFormMixin
from accounts.models import User
from academics.models import Enrollment, SchoolClass, Term

from .models import Parent, Student


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
            'student_id', 'school_class', 'parent', 'admission_date', 'date_of_birth',
            'gender', 'status', 'address', 'guardian_name', 'guardian_phone',
            'blood_group', 'medical_notes',
        ]
        widgets = {
            'admission_date': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'medical_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_id'].help_text = 'Leave blank to generate automatically.'
        self.fields['parent'].queryset = Parent.objects.select_related('user')
        self.fields['school_class'].queryset = SchoolClass.objects.select_related(
            'academic_year'
        ).order_by('name')
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
