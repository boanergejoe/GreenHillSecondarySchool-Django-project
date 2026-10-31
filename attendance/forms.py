from django import forms
from django.utils import timezone

from academics.models import SchoolClass, Subject
from accounts.forms import BootstrapFormMixin


class AttendanceFilterForm(BootstrapFormMixin, forms.Form):
    school_class = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.prefetch_related('school_classes').all(),
        required=False,
    )
    date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school_class'].queryset = SchoolClass.objects.order_by('name')
        self.fields['subject'].queryset = Subject.objects.prefetch_related(
            'school_classes'
        ).order_by('name')
