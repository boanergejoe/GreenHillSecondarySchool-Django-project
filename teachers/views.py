from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView

from accounts.mixins import user_has_role
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView

from .forms import TeacherForm
from .models import Teacher


class TeacherListView(BaseListView):
    model = Teacher
    page_title = 'Teachers / Lecturers'
    allowed_roles = ('accountant',)
    search_fields = [
        'staff_id', 'user__first_name', 'user__last_name', 'user__email',
        'specialization', 'department__name',
    ]
    columns = [
        ('Staff ID', 'staff_id'),
        ('Full Name', 'user.display_name'),
        ('Department', 'department.name'),
        ('Specialization', 'specialization'),
        ('Employment', 'get_employment_type_display'),
        ('Status', 'get_status_display'),
    ]
    create_url_name = 'teachers:teacher_create'
    edit_url_name = 'teachers:teacher_update'
    delete_url_name = 'teachers:teacher_delete'
    detail_url_name = 'teachers:teacher_detail'
    create_label = 'Add Teacher'

    def get_queryset(self):
        qs = Teacher.objects.select_related('user', 'department')
        q = self.request.GET.get('q', '').strip()
        dept = self.request.GET.get('department', '').strip()
        status = self.request.GET.get('status', '').strip()
        if q:
            qs = qs.filter(
                Q(staff_id__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(specialization__icontains=q)
            )
        if dept:
            qs = qs.filter(department_id=dept)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        from academics.models import Department

        context = super().get_context_data(**kwargs)
        context.update({
            'departments': Department.objects.all(),
            'selected_department': self.request.GET.get('department', ''),
            'selected_status': self.request.GET.get('status', ''),
            'status_choices': Teacher.Status.choices,
        })
        return context


class TeacherCreateView(BaseCreateView):
    model = Teacher
    form_class = TeacherForm
    page_title = 'Add Teacher / Lecturer'
    success_url = reverse_lazy('teachers:teacher_list')
    cancel_url_name = 'teachers:teacher_list'
    success_message = 'Teacher account created successfully.'


class TeacherUpdateView(BaseUpdateView):
    model = Teacher
    form_class = TeacherForm
    page_title = 'Edit Teacher / Lecturer'
    success_url = reverse_lazy('teachers:teacher_list')
    cancel_url_name = 'teachers:teacher_list'
    success_message = 'Teacher account updated successfully.'


class TeacherDeleteView(BaseDeleteView):
    model = Teacher
    page_title = 'Delete Teacher / Lecturer'
    success_url = reverse_lazy('teachers:teacher_list')
    cancel_url_name = 'teachers:teacher_list'

    def form_valid(self, form):
        user = self.object.user
        response = super().form_valid(form)
        if user:
            user.delete()
        return response


class TeacherDetailView(DetailView):
    model = Teacher
    template_name = 'teachers/teacher_detail.html'
    context_object_name = 'teacher'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        teacher = get_object_or_404(Teacher, pk=kwargs['pk'])
        allowed = user_has_role(request.user, ('accountant',)) or (
            request.user.role == 'teacher' and teacher.user_id == request.user.id
        )
        if not allowed:
            raise PermissionDenied('You cannot view this teacher record.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Teacher.objects.select_related('user', 'department')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': f'Teacher - {self.object.full_name}',
            'subjects': self.object.user.teaching_subjects.select_related(
                'school_class'
            ),
            'managed_classes': self.object.user.managed_classes.all(),
            'assignments': self.object.user.created_assignments.select_related(
                'subject'
            )[:10],
        })
        return context
