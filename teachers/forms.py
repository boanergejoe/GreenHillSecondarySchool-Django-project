from django import forms

from accounts.forms import BootstrapFormMixin, UserAccountFormMixin
from accounts.models import User

from academics.models import SchoolClass

from .models import Teacher


class TeacherForm(UserAccountFormMixin, BootstrapFormMixin, forms.ModelForm):
    assigned_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        label='Classes to teach',
    )

    class Meta:
        model = Teacher
        fields = [
            'staff_id', 'department', 'assigned_classes', 'qualification', 'specialization',
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
        self.fields['assigned_classes'].queryset = SchoolClass.objects.select_related(
            'academic_year'
        ).order_by('-academic_year__start_date', 'name')

    def save(self, commit=True):
        user = self.save_user(User.Role.TEACHER, commit=commit)
        teacher = super().save(commit=False)
        teacher.user = user
        if commit:
            teacher.save()
            self.save_m2m()
        return teacher
