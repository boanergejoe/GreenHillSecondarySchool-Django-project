from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def user_has_role(user, roles):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == 'admin':
        return True
    return user.role in roles


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()
    permission_denied_message = 'You do not have permission to access this page.'

    def test_func(self):
        return user_has_role(self.request.user, self.allowed_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied(self.permission_denied_message)


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if not user_has_role(request.user, roles):
                raise PermissionDenied('You do not have permission to access this page.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
