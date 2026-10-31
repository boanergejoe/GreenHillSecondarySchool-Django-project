from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Announcement, Notification


class AnnouncementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            'title', 'message', 'audience', 'attachment', 'event_date', 'is_published',
        ]
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
            'event_date': forms.DateInput(attrs={'type': 'date'}),
        }


class NotificationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['user', 'title', 'message', 'link']
        widgets = {'message': forms.Textarea(attrs={'rows': 3})}
