from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView

from accounts.forms import BootstrapFormMixin
from accounts.mixins import role_required, user_has_role
from academics.access import teacher_can_access_student, teacher_classes
from academics.models import AcademicYear, SchoolClass
from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView

from .forms import ParentForm, StudentForm
from .models import Parent, Student


def can_view_student(user, student):
    if user_has_role(user, ('accountant',)):
        return True
    if user.role == 'teacher':
        return teacher_can_access_student(user, student)
    if user.role == 'student':
        return student.user_id == user.id
    if user.role == 'parent':
        return student.parent_id and student.parent.user_id == user.id
    return False


class StudentListView(BaseListView):
    model = Student
    page_title = 'Students'
    allowed_roles = ('teacher', 'accountant')
    search_fields = [
        'student_id', 'user__first_name', 'user__last_name', 'user__email',
        'user__username', 'department__name',
    ]
    columns = [
        ('Student ID', 'student_id'),
        ('Full Name', 'user.display_name'),
        ('Class', 'school_class.name'),
        ('Department', 'department.name'),
        ('Gender', 'get_gender_display'),
        ('Status', 'get_status_display'),
        ('Admitted', 'admission_date'),
    ]
    create_url_name = 'students:student_create'
    edit_url_name = 'students:student_update'
    delete_url_name = 'students:student_delete'
    detail_url_name = 'students:student_detail'
    create_label = 'Register Student'
    create_roles = ('accountant',)

    def get_queryset(self):
        qs = Student.objects.select_related('user', 'school_class', 'department')
        q = self.request.GET.get('q', '').strip()
        class_id = self.request.GET.get('school_class', '').strip()
        status = self.request.GET.get('status', '').strip()
        if self.request.user.role == 'teacher':
            qs = qs.filter(school_class__in=teacher_classes(self.request.user))
        if q:
            qs = qs.filter(
                Q(student_id__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(user__username__icontains=q)
            )
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classes = SchoolClass.objects.all().order_by('name')
        if self.request.user.role == 'teacher':
            classes = teacher_classes(self.request.user).order_by('name')
        context.update({
            'classes': classes,
            'selected_class': self.request.GET.get('school_class', ''),
            'selected_status': self.request.GET.get('status', ''),
            'status_choices': Student.Status.choices,
        })
        return context


class StudentCreateView(BaseCreateView):
    model = Student
    form_class = StudentForm
    page_title = 'Register Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    success_message = 'Student registered successfully.'
    allowed_roles = ('accountant',)


class StudentUpdateView(BaseUpdateView):
    model = Student
    form_class = StudentForm
    page_title = 'Edit Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    success_message = 'Student record updated successfully.'
    allowed_roles = ('accountant',)


class StudentDeleteView(BaseDeleteView):
    model = Student
    page_title = 'Delete Student'
    success_url = reverse_lazy('students:student_list')
    cancel_url_name = 'students:student_list'
    allowed_roles = ('accountant',)

    def form_valid(self, form):
        user = self.object.user
        response = super().form_valid(form)
        if user:
            user.delete()
        return response


class StudentDetailView(DetailView):
    model = Student
    template_name = 'students/student_detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        student = get_object_or_404(Student, pk=kwargs['pk'])
        if not can_view_student(request.user, student):
            raise PermissionDenied('You cannot view this student record.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Student.objects.select_related(
            'user', 'school_class', 'department', 'parent__user'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        results = student.results.select_related('subject', 'examination')
        if self.request.user.role in ('student', 'parent'):
            results = results.filter(examination__is_published=True)
        context.update({
            'page_title': f'Student - {student.full_name}',
            'results': results[:10],
            'attendance': student.attendance_records.select_related('subject')[:10],
            'payments': student.payments.select_related('fee')[:10],
            'submissions': student.submissions.select_related('assignment')[:10],
            'can_view_medical_data': user_has_role(
                self.request.user, ('accountant',)
            ),
            'attendance_percentage': student.attendance_percentage,
            'enrollments': student.enrollments.select_related(
                'school_class', 'academic_year'
            ).order_by('-enrolled_on'),
        })
        return context


class ParentListView(BaseListView):
    model = Parent
    page_title = 'Parents / Guardians'
    allowed_roles = ('accountant',)
    search_fields = [
        'user__first_name', 'user__last_name', 'user__email', 'user__phone',
    ]
    columns = [
        ('Name', 'user.display_name'),
        ('Relationship', 'get_relationship_display'),
        ('Phone', 'user.phone'),
        ('Email', 'user.email'),
        ('Children', 'children_count'),
    ]
    create_url_name = 'students:parent_create'
    edit_url_name = 'students:parent_update'
    delete_url_name = 'students:parent_delete'
    detail_url_name = 'students:parent_detail'
    create_label = 'Add Parent'
    create_roles = ('accountant',)

    def get_queryset(self):
        return Parent.objects.select_related('user').prefetch_related('children')


class ParentCreateView(BaseCreateView):
    model = Parent
    form_class = ParentForm
    page_title = 'Add Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    success_message = 'Parent account created successfully.'
    allowed_roles = ('accountant',)


class ParentUpdateView(BaseUpdateView):
    model = Parent
    form_class = ParentForm
    page_title = 'Edit Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    success_message = 'Parent account updated successfully.'
    allowed_roles = ('accountant',)


class ParentDeleteView(BaseDeleteView):
    model = Parent
    page_title = 'Delete Parent / Guardian'
    success_url = reverse_lazy('students:parent_list')
    cancel_url_name = 'students:parent_list'
    allowed_roles = ('accountant',)

    def form_valid(self, form):
        user = self.object.user
        response = super().form_valid(form)
        if user:
            user.delete()
        return response


class ParentDetailView(DetailView):
    model = Parent
    template_name = 'students/parent_detail.html'
    context_object_name = 'parent'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        parent = get_object_or_404(Parent, pk=kwargs['pk'])
        allowed = user_has_role(request.user, ('accountant',)) or (
            request.user.role == 'parent' and parent.user_id == request.user.id
        )
        if not allowed:
            raise PermissionDenied('You cannot view this parent record.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Parent.objects.select_related('user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Parent - {self.object.user.display_name}'
        context['children'] = self.object.children.select_related('user', 'school_class')
        return context


class PromoteForm(BootstrapFormMixin, forms.Form):
    from_class = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    to_class = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.all())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_class') == cleaned.get('to_class'):
            raise forms.ValidationError('The destination class must be different.')
        return cleaned


@role_required()
def promote_students(request):
    form = PromoteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from_class = form.cleaned_data['from_class']
        to_class = form.cleaned_data['to_class']
        count = Student.objects.filter(
            school_class=from_class, status=Student.Status.ACTIVE
        ).update(school_class=to_class)
        messages.success(request, f'{count} student(s) promoted to {to_class.name}.')
        return redirect('students:student_list')
    return render(request, 'students/promote.html', {
        'form': form,
        'page_title': 'Promote Students',
        'cancel_url': '/students/',
    })
