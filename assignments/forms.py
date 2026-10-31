from django import forms

from academics.models import Subject
from accounts.forms import BootstrapFormMixin

from .models import Assignment, Submission


class AssignmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            'subject', 'title', 'description', 'attachment', 'due_date',
            'max_score', 'is_published',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        qs = Subject.objects.select_related(
            'academic_year'
        ).prefetch_related('school_classes')
        if self.user and self.user.role == 'teacher':
            qs = qs.filter(teacher=self.user)
        self.fields['subject'].queryset = qs.order_by('name')


class SubmissionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file', 'comment']


class ReviewSubmissionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['score', 'feedback', 'status']
        widgets = {'feedback': forms.Textarea(attrs={'rows': 3})}
