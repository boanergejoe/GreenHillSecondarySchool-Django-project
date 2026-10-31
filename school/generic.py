from django import forms
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.shortcuts import resolve_url
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import RoleRequiredMixin, user_has_role

GENERATED_FIELD_NAMES = {'id', 'pk', 'student_id', 'staff_id', 'receipt_number'}


def mark_required_fields(form, exclusions=()):
    for name, field in form.fields.items():
        widget = field.widget
        if (
            name in GENERATED_FIELD_NAMES
            or name in exclusions
            or field.disabled
            or widget.is_hidden
            or isinstance(widget, (forms.CheckboxInput, forms.FileInput))
        ):
            continue
        if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
            field.required = True
            widget.attrs.pop('required', None)
            widget.attrs.pop('aria-required', None)
            continue
        field.required = True
        widget.attrs['required'] = 'required'
        widget.attrs['aria-required'] = 'true'


class RequiredCreateFieldsMixin:
    required_field_exclusions = ()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        mark_required_fields(form, self.required_field_exclusions)
        return form


class BaseListView(RoleRequiredMixin, ListView):
    template_name = 'core/list.html'
    context_object_name = 'objects'
    paginate_by = 10
    allowed_roles = ()
    search_fields = []
    columns = []
    page_title = ''
    create_url_name = None
    edit_url_name = None
    delete_url_name = None
    detail_url_name = None
    create_label = 'Add New'
    create_roles = ()
    empty_message = 'No records found.'

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f'{field}__icontains': q})
            queryset = queryset.filter(condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update({
            'page_title': self.page_title,
            'columns': self.columns,
            'q': self.request.GET.get('q', ''),
            'create_url_name': self.create_url_name,
            'edit_url_name': self.edit_url_name,
            'delete_url_name': self.delete_url_name,
            'detail_url_name': self.detail_url_name,
            'create_label': self.create_label,
            'empty_message': self.empty_message,
            'querystring': params.urlencode(),
            'total_count': self.get_queryset().count(),
            'can_create': user_has_role(self.request.user, self.create_roles),
        })
        return context


class BaseCreateView(RequiredCreateFieldsMixin, RoleRequiredMixin, SuccessMessageMixin, CreateView):
    template_name = 'core/form.html'
    allowed_roles = ()
    page_title = 'Add Record'
    cancel_url_name = None
    success_message = 'Record was created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['cancel_url'] = (
            resolve_url(self.cancel_url_name) if self.cancel_url_name else None
        )
        return context


class BaseUpdateView(RoleRequiredMixin, SuccessMessageMixin, UpdateView):
    template_name = 'core/form.html'
    allowed_roles = ()
    page_title = 'Edit Record'
    cancel_url_name = None
    success_message = 'Record was updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['cancel_url'] = (
            resolve_url(self.cancel_url_name) if self.cancel_url_name else None
        )
        return context


class BaseDeleteView(RoleRequiredMixin, DeleteView):
    template_name = 'core/confirm_delete.html'
    allowed_roles = ()
    page_title = 'Delete Record'
    cancel_url_name = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['cancel_url'] = (
            resolve_url(self.cancel_url_name) if self.cancel_url_name else None
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Record was deleted successfully.')
        return super().form_valid(form)
