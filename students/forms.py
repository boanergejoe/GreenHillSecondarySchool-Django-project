from django import forms

from accounts.forms import BootstrapFormMixin, UserAccountFormMixin
from accounts.models import User

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

    def save(self, commit=True):
        user = self.save_user(User.Role.STUDENT, commit=commit)
        student = super().save(commit=False)
        student.user = user
        if commit:
            student.save()
            self.save_m2m()
        return student
