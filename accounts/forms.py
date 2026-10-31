from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class BootstrapFormMixin:
    """Applies Bootstrap 5 classes to all widgets on a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')
            if field.required:
                widget.attrs.setdefault('required', 'required')


class StyledLoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'autofocus': True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'})
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_active:
            raise forms.ValidationError('This account has been disabled.', code='inactive')


class StaffForm(BootstrapFormMixin, forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Leave blank when editing to keep the current password.',
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'phone',
            'address', 'role', 'photo', 'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk is None:
            self.fields['role'].choices = [
                (User.Role.ADMIN, 'Super Administrator'),
                (User.Role.ACCOUNTANT, 'Accountant'),
            ]
        else:
            self.fields['role'].choices = [
                (User.Role.ADMIN, 'Super Administrator'),
                (User.Role.ACCOUNTANT, 'Accountant'),
                (User.Role.TEACHER, 'Teacher / Lecturer'),
            ]

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.instance.pk and not password:
            raise forms.ValidationError('A password is required for new accounts.')
        if password and len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'photo']


def _account_fields():
    return {
        'username': forms.CharField(label='Username', max_length=150),
        'first_name': forms.CharField(label='First name', max_length=150),
        'last_name': forms.CharField(label='Last name', max_length=150),
        'email': forms.EmailField(label='Email', required=False),
        'phone': forms.CharField(label='Phone', max_length=30, required=False),
        'photo': forms.ImageField(label='Photo', required=False),
        'password': forms.CharField(
            label='Password',
            required=False,
            widget=forms.PasswordInput(render_value=False),
            help_text='Leave blank to keep the current password.',
        ),
    }


class UserAccountFormMixin:
    """Mixin for profile forms that also create/update the linked user account."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account_fields = _account_fields()
        self.fields = {**account_fields, **self.fields}
        for name in account_fields:
            field = self.fields[name]
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')
            if field.required:
                widget.attrs.setdefault('required', 'required')

        user = getattr(self.instance, 'user', None) if self.instance.pk else None
        if user:
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = user.phone
            self.fields['photo'].initial = user.photo
        else:
            self.fields['password'].required = True
            self.fields['password'].help_text = 'Minimum 8 characters.'

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.instance.pk and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters.')
        return password

    def save_user(self, role, commit=True):
        user = self.instance.user if self.instance.pk else User()
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data.get('email', '')
        user.phone = self.cleaned_data.get('phone', '')
        user.role = role
        if self.cleaned_data.get('photo'):
            user.photo = self.cleaned_data['photo']
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
