from django.urls import reverse_lazy

from school.generic import BaseCreateView, BaseDeleteView, BaseListView, BaseUpdateView

from .forms import (
    AcademicYearForm, DepartmentForm, EnrollmentForm, SchoolClassForm,
    SubjectForm, TermForm,
)
from .models import (
    AcademicYear, Department, Enrollment, SchoolClass, Subject, Term,
)


class DepartmentListView(BaseListView):
    model = Department
    page_title = 'Departments'
    search_fields = ['name', 'code']
    columns = [('Name', 'name'), ('Code', 'code'), ('Description', 'description')]
    create_url_name = 'academics:department_create'
    edit_url_name = 'academics:department_update'
    delete_url_name = 'academics:department_delete'
    create_label = 'Add Department'


class DepartmentCreateView(BaseCreateView):
    model = Department
    form_class = DepartmentForm
    page_title = 'Add Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'


class DepartmentUpdateView(BaseUpdateView):
    model = Department
    form_class = DepartmentForm
    page_title = 'Edit Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'


class DepartmentDeleteView(BaseDeleteView):
    model = Department
    page_title = 'Delete Department'
    success_url = reverse_lazy('academics:department_list')
    cancel_url_name = 'academics:department_list'


class AcademicYearListView(BaseListView):
    model = AcademicYear
    page_title = 'Academic Years'
    search_fields = ['name']
    columns = [
        ('Name', 'name'), ('Start Date', 'start_date'), ('End Date', 'end_date'),
        ('Current', 'is_current'),
    ]
    create_url_name = 'academics:year_create'
    edit_url_name = 'academics:year_update'
    delete_url_name = 'academics:year_delete'
    create_label = 'Add Academic Year'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['term_list_url'] = reverse_lazy('academics:term_list')
        return context


class AcademicYearCreateView(BaseCreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    page_title = 'Add Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'
    required_field_exclusions = tuple(
        field
        for term_index in range(1, 4)
        for field in (
            f'term_{term_index}_start_date',
            f'term_{term_index}_end_date',
        )
    )


class AcademicYearUpdateView(BaseUpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    page_title = 'Edit Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'


class AcademicYearDeleteView(BaseDeleteView):
    model = AcademicYear
    page_title = 'Delete Academic Year'
    success_url = reverse_lazy('academics:year_list')
    cancel_url_name = 'academics:year_list'


class TermListView(BaseListView):
    model = Term
    page_title = 'Terms'
    search_fields = ['name', 'academic_year__name']
    columns = [
        ('Term', 'name'), ('Academic Year', 'academic_year.name'),
        ('Start Date', 'start_date'), ('End Date', 'end_date'), ('Current', 'is_current'),
    ]
    create_url_name = 'academics:term_create'
    edit_url_name = 'academics:term_update'
    delete_url_name = 'academics:term_delete'
    create_label = 'Add Term'


class TermCreateView(BaseCreateView):
    model = Term
    form_class = TermForm
    page_title = 'Add Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'


class TermUpdateView(BaseUpdateView):
    model = Term
    form_class = TermForm
    page_title = 'Edit Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'


class TermDeleteView(BaseDeleteView):
    model = Term
    page_title = 'Delete Term'
    success_url = reverse_lazy('academics:term_list')
    cancel_url_name = 'academics:term_list'


class SchoolClassListView(BaseListView):
    model = SchoolClass
    page_title = 'Classes'
    allowed_roles = ('teacher', 'accountant')
    search_fields = ['name', 'level', 'stream', 'room']
    columns = [
        ('Class', 'name'), ('Level', 'level'), ('Stream', 'stream'),
        ('Department', 'department.name'), ('Academic Year', 'academic_year.name'),
        ('Class Teacher', 'class_teacher.display_name'), ('Students', 'student_count'),
        ('Capacity', 'capacity'),
    ]
    create_url_name = 'academics:class_create'
    edit_url_name = 'academics:class_update'
    delete_url_name = 'academics:class_delete'
    create_label = 'Add Class'


class SchoolClassCreateView(BaseCreateView):
    model = SchoolClass
    form_class = SchoolClassForm
    page_title = 'Add Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'
    required_field_exclusions = ('stream', 'department', 'class_teacher')


class SchoolClassUpdateView(BaseUpdateView):
    model = SchoolClass
    form_class = SchoolClassForm
    page_title = 'Edit Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'


class SchoolClassDeleteView(BaseDeleteView):
    model = SchoolClass
    page_title = 'Delete Class'
    success_url = reverse_lazy('academics:class_list')
    cancel_url_name = 'academics:class_list'


class SubjectListView(BaseListView):
    model = Subject
    page_title = 'Subjects'
    allowed_roles = ('teacher', 'accountant')
    search_fields = [
        'name', 'code', 'school_classes__name', 'teacher__first_name',
        'departments__name',
    ]
    columns = [
        ('Code', 'code'), ('Subject', 'name'),
        ('Department(s)', 'department_names'), ('Class(es)', 'school_class_names'),
        ('Teacher', 'teacher.display_name'), ('Academic Year', 'academic_year.name'),
        ('Term', 'term'), ('Active', 'is_active'),
    ]
    create_url_name = 'academics:subject_create'
    edit_url_name = 'academics:subject_update'
    delete_url_name = 'academics:subject_delete'
    create_label = 'Add Subject'

    def get_queryset(self):
        qs = Subject.objects.select_related(
            'teacher', 'academic_year'
        ).prefetch_related('departments')
        qs = qs.prefetch_related('school_classes')
        if self.request.user.role == 'teacher':
            qs = qs.filter(teacher=self.request.user)
        return qs


class SubjectCreateView(BaseCreateView):
    model = Subject
    form_class = SubjectForm
    page_title = 'Add Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'


class SubjectUpdateView(BaseUpdateView):
    model = Subject
    form_class = SubjectForm
    page_title = 'Edit Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'


class SubjectDeleteView(BaseDeleteView):
    model = Subject
    page_title = 'Delete Subject'
    success_url = reverse_lazy('academics:subject_list')
    cancel_url_name = 'academics:subject_list'


class EnrollmentListView(BaseListView):
    model = Enrollment
    page_title = 'Enrollments'
    allowed_roles = ('teacher', 'accountant')
    search_fields = ['student__user__first_name', 'student__student_id']
    columns = [
        ('Student', 'student.user.display_name'), ('Student ID', 'student.student_id'),
        ('Class', 'school_class.name'), ('Academic Year', 'academic_year.name'),
        ('Term', 'term'), ('Enrolled On', 'enrolled_on'),
        ('Active', 'is_active'),
    ]
    create_url_name = 'academics:enrollment_create'
    edit_url_name = 'academics:enrollment_update'
    delete_url_name = 'academics:enrollment_delete'
    create_label = 'Add Enrollment'


class EnrollmentCreateView(BaseCreateView):
    model = Enrollment
    form_class = EnrollmentForm
    page_title = 'Add Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'


class EnrollmentUpdateView(BaseUpdateView):
    model = Enrollment
    form_class = EnrollmentForm
    page_title = 'Edit Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'


class EnrollmentDeleteView(BaseDeleteView):
    model = Enrollment
    page_title = 'Delete Enrollment'
    success_url = reverse_lazy('academics:enrollment_list')
    cancel_url_name = 'academics:enrollment_list'
