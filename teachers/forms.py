from django import forms

from accounts.forms import BootstrapFormMixin, UserAccountFormMixin
from accounts.models import User

from .models import Teacher


class TeacherForm(UserAccountFormMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            'staff_id', 'department', 'qualification', 'specialization',
            'employment_type', 'status', 'date_joined', 'office', 'bio',
        ]
        widgets = {
            'date_joined': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff_id'].help_text = 'Leave blank to generate automatically.'
        self.fields['department'].queryset = self.fields['department'].queryset.order_by('name')

    def save(self, commit=True):
        user = self.save_user(User.Role.TEACHER, commit=commit)
        teacher = super().save(commit=False)
        teacher.user = user
        if commit:
            teacher.save()
            self.save_m2m()
        return teacher
