from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academics.access import teacher_classes
from academics.forms import EnrollmentForm, SubjectForm, TermForm
from academics.models import (
    AcademicYear, Department, Enrollment, SchoolClass, Subject, Term,
)
from accounts.models import User
from assignments.models import Assignment
from attendance.models import Attendance
from communications.models import Announcement
from examinations.forms import ExaminationForm
from examinations.models import Examination, Result
from finance.forms import FeeForm
from finance.models import Fee, Payment
from finance.services import active_fees_for_student
from students.forms import StudentForm
from students.models import Parent, Student
from teachers.models import Teacher


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
)
class GreenHillSecondaryIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)

    def login(self, username):
        user = User.objects.get(username=username)
        self.client.force_login(user)
        return user

    def test_all_role_dashboards_render(self):
        for username in ('admin', 'teacher1', 'student1', 'parent1', 'accountant'):
            self.login(username)
            response = self.client.get(reverse('accounts:dashboard'))
            self.assertEqual(response.status_code, 200, username)

    def test_admin_management_pages_render(self):
        self.login('admin')
        urls = [
            reverse('accounts:user_list'),
            reverse('accounts:user_create'),
            reverse('students:student_list'),
            reverse('students:student_create'),
            reverse('students:parent_list'),
            reverse('students:parent_create'),
            reverse('students:student_promote'),
            reverse('teachers:teacher_list'),
            reverse('teachers:teacher_create'),
            reverse('academics:department_list'),
            reverse('academics:year_list'),
            reverse('academics:term_list'),
            reverse('academics:class_list'),
            reverse('academics:subject_list'),
            reverse('academics:enrollment_list'),
            reverse('attendance:take'),
            reverse('examinations:exam_list'),
            reverse('examinations:exam_create'),
            reverse('finance:fee_list'),
            reverse('finance:fee_create'),
            reverse('finance:payment_list'),
            reverse('finance:payment_create'),
            reverse('finance:financial_overview'),
            reverse('assignments:create'),
            reverse('communications:announcement_create'),
            reverse('reports:index'),
            reverse('reports:class_performance'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_django_admin_change_lists_render(self):
        self.login('admin')
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)

        for model in admin.site._registry:
            url = reverse(
                f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_accountant_can_manage_student_and_parent_records(self):
        self.login('accountant')
        student = Student.objects.select_related('school_class').first()
        parent = Parent.objects.first()
        urls = [
            reverse('students:student_list'),
            reverse('students:student_create'),
            reverse('students:student_detail', args=[student.pk]),
            reverse('students:student_update', args=[student.pk]),
            reverse('students:parent_list'),
            reverse('students:parent_create'),
            reverse('students:parent_detail', args=[parent.pk]),
            reverse('finance:fee_statement', args=[student.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_accountant_can_load_fee_list_after_sign_in(self):
        self.login('accountant')
        response = self.client.get(reverse('finance:fee_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fee Structure')
        self.assertContains(response, 'Registration Fee')

    def test_teacher_dashboard_and_lists_render(self):
        self.login('teacher1')
        urls = [
            reverse('accounts:dashboard'),
            reverse('students:student_list'),
            reverse('examinations:exam_list'),
            reverse('academics:subject_list'),
            reverse('attendance:list'),
            reverse('reports:index'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_student_can_access_own_records(self):
        user = self.login('student1')
        student = user.student_profile
        exam = Examination.objects.filter(school_class=student.school_class).first()
        assignment = Assignment.objects.filter(
            subject__school_classes=student.school_class
        ).first()
        urls = [
            reverse('students:student_detail', args=[student.pk]),
            reverse('finance:fee_statement', args=[student.pk]),
            reverse('examinations:report_card', args=[student.pk, exam.pk]),
            reverse('assignments:detail', args=[assignment.pk]),
            reverse('assignments:submit', args=[assignment.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_student_cannot_access_other_records(self):
        user = self.login('student1')
        other = Student.objects.exclude(pk=user.student_profile.pk).first()
        other_exam = Examination.objects.first()
        response = self.client.get(reverse('students:student_detail', args=[other.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('finance:fee_statement', args=[other.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            reverse('examinations:report_card', args=[other.pk, other_exam.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_parent_can_access_own_children(self):
        user = self.login('parent1')
        parent = user.parent_profile
        student = parent.children.select_related('school_class').first()
        exam = Examination.objects.filter(school_class=student.school_class).first()
        assignment = Assignment.objects.filter(
            subject__school_classes=student.school_class
        ).first()
        urls = [
            reverse('students:student_detail', args=[student.pk]),
            reverse('finance:fee_statement', args=[student.pk]),
            reverse('examinations:report_card', args=[student.pk, exam.pk]),
            reverse('students:parent_detail', args=[parent.pk]),
            reverse('assignments:detail', args=[assignment.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_parent_cannot_access_other_records(self):
        user = self.login('parent1')
        other = Student.objects.exclude(parent=user.parent_profile).first()
        other_parent = Parent.objects.exclude(pk=user.parent_profile.pk).first()
        response = self.client.get(reverse('students:student_detail', args=[other.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('students:parent_detail', args=[other_parent.pk]))
        self.assertEqual(response.status_code, 403)

    def test_student_health_details_are_hidden_from_parent_and_student(self):
        student = User.objects.get(username='student1').student_profile
        student.blood_group = 'AB+'
        student.medical_notes = 'Sensitive medical test note.'
        student.save(update_fields=['blood_group', 'medical_notes'])

        parent = self.login('parent1')
        response = self.client.get(reverse('students:student_detail', args=[student.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'AB+')
        self.assertNotContains(response, 'Sensitive medical test note.')

        self.login('student1')
        response = self.client.get(reverse('students:student_detail', args=[student.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'AB+')
        self.assertNotContains(response, 'Sensitive medical test note.')

        self.login('accountant')
        response = self.client.get(reverse('students:student_detail', args=[student.pk]))
        self.assertContains(response, 'AB+')
        self.assertContains(response, 'Sensitive medical test note.')

    def test_teacher_records_attendance_and_parent_can_view_child_record(self):
        teacher = self.login('teacher1')
        student = Student.objects.filter(
            school_class__in=teacher_classes(teacher),
            parent__isnull=False,
            status=Student.Status.ACTIVE,
        ).select_related('parent__user', 'school_class').first()
        self.assertIsNotNone(student)
        selected_date = timezone.localdate()
        classmates = Student.objects.filter(
            school_class=student.school_class,
            status=Student.Status.ACTIVE,
        )
        post_data = {
            'school_class': student.school_class_id,
            'date': selected_date.isoformat(),
            'subject': '',
        }
        post_data.update({
            f'status_{classmate.pk}': (
                Attendance.Status.ABSENT
                if classmate.pk == student.pk else Attendance.Status.PRESENT
            )
            for classmate in classmates
        })

        response = self.client.post(reverse('attendance:take'), post_data)
        self.assertRedirects(response, reverse('attendance:list'))
        record = Attendance.objects.get(
            student=student, school_class=student.school_class, date=selected_date,
            subject=None,
        )
        self.assertEqual(record.status, Attendance.Status.ABSENT)
        self.assertEqual(record.recorded_by, teacher)

        self.client.force_login(student.parent.user)
        response = self.client.get(reverse('attendance:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.student_id)
        self.assertContains(response, 'Absent')

    def test_accountant_records_payment_and_parent_can_download_receipt(self):
        parent = Parent.objects.get(user__username='parent1')
        student = parent.children.select_related('user', 'school_class').first()
        fee = active_fees_for_student(student).first()
        self.assertIsNotNone(fee)
        accountant = self.login('accountant')
        response = self.client.post(reverse('finance:payment_create'), {
            'student': student.pk,
            'fee': fee.pk,
            'amount': '2500.00',
            'payment_date': timezone.localdate().isoformat(),
            'method': Payment.Method.CASH,
            'reference': 'E2E-PAYMENT-001',
            'remarks': 'Workflow test payment',
        })
        self.assertRedirects(response, reverse('finance:payment_list'))
        payment = Payment.objects.get(reference='E2E-PAYMENT-001')
        self.assertTrue(payment.receipt_number)
        self.assertEqual(payment.recorded_by, accountant)

        self.client.force_login(parent.user)
        response = self.client.get(reverse('finance:fee_statement', args=[student.pk]))
        self.assertContains(response, payment.receipt_number)
        response = self.client.get(reverse('finance:payment_detail', args=[payment.pk]))
        self.assertContains(response, payment.receipt_number)
        response = self.client.get(reverse('finance:receipt_pdf', args=[payment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_results_are_hidden_until_teacher_entry_is_published(self):
        teacher = self.login('teacher1')
        school_class = Examination.objects.filter(
            school_class__in=teacher_classes(teacher)
        ).values_list('school_class_id', flat=True).first()
        self.assertIsNotNone(school_class)
        exam = Examination.objects.filter(school_class_id=school_class).first()
        student = Student.objects.filter(
            school_class_id=school_class,
            parent__isnull=False,
            status=Student.Status.ACTIVE,
        ).select_related('parent__user').first()
        subject = Subject.objects.filter(
            academic_year=exam.academic_year,
            school_classes=school_class,
        ).first()
        self.assertIsNotNone(student)
        self.assertIsNotNone(subject)
        Examination.objects.filter(pk=exam.pk).update(is_published=False)
        exam.refresh_from_db()

        response = self.client.post(
            reverse('examinations:enter_results', args=[exam.pk]),
            {
                'subject': subject.pk,
                f'marks_{student.pk}': '77',
            },
        )
        self.assertRedirects(
            response, reverse('examinations:exam_detail', args=[exam.pk])
        )
        result = Result.objects.get(
            student=student, examination=exam, subject=subject
        )
        self.assertEqual(result.marks_obtained, Decimal('77'))

        self.client.force_login(student.parent.user)
        response = self.client.get(reverse('examinations:result_list'))
        self.assertFalse(response.context['results'].filter(pk=result.pk).exists())
        response = self.client.get(
            reverse('examinations:report_card', args=[student.pk, exam.pk])
        )
        self.assertEqual(response.status_code, 403)

        admin = User.objects.get(username='admin')
        self.client.force_login(admin)
        response = self.client.post(
            reverse('examinations:exam_update', args=[exam.pk]),
            {
                'name': exam.name,
                'exam_type': exam.exam_type,
                'academic_year': exam.academic_year_id,
                'term': exam.term_id,
                'school_class': exam.school_class_id,
                'start_date': exam.start_date.isoformat(),
                'end_date': exam.end_date.isoformat(),
                'total_marks': exam.total_marks,
                'is_published': 'on',
            },
        )
        self.assertRedirects(response, reverse('examinations:exam_list'))

        self.client.force_login(student.parent.user)
        response = self.client.get(reverse('examinations:result_list'))
        self.assertTrue(response.context['results'].filter(pk=result.pk).exists())
        response = self.client.get(
            reverse('examinations:report_card', args=[student.pk, exam.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_student_create_form_creates_linked_user(self):
        self.login('admin')
        school_class = SchoolClass.objects.first()
        parent = Parent.objects.first()
        department = Department.objects.get(code='ART')
        terms = list(Term.objects.filter(
            academic_year=school_class.academic_year
        ).order_by('name')[:2])
        response = self.client.post(reverse('students:student_create'), {
            'username': 'newstudent',
            'first_name': 'Amina',
            'last_name': 'Kiden',
            'email': 'amina@example.com',
            'phone': '+211900111222',
            'password': 'Student@12345',
            'student_id': '',
            'school_class': school_class.pk,
            'department': department.pk,
            'term': [term.name for term in terms],
            'parent': parent.pk,
            'admission_date': timezone.localdate().isoformat(),
            'date_of_birth': '2008-01-01',
            'gender': 'female',
            'status': 'active',
            'address': 'Juba',
            'guardian_name': 'Peter Kiden',
            'guardian_phone': '+211900777888',
            'blood_group': 'O+',
            'medical_notes': 'No known conditions',
        })
        self.assertRedirects(response, reverse('students:student_list'))
        user = User.objects.get(username='newstudent')
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password('Student@12345'))
        self.assertEqual(user.student_profile.school_class, school_class)
        self.assertEqual(user.student_profile.department, department)
        enrollments = Enrollment.objects.filter(student=user.student_profile)
        self.assertEqual(enrollments.count(), len(terms))
        self.assertSetEqual(
            set(enrollments.values_list('term', flat=True)),
            {term.name for term in terms},
        )
        self.assertEqual(
            set(enrollments.values_list('academic_year_id', flat=True)),
            {school_class.academic_year_id},
        )

    def test_teacher_create_form_creates_linked_user(self):
        self.login('admin')
        department = Department.objects.first()
        school_classes = list(SchoolClass.objects.all()[:2])
        form_response = self.client.get(reverse('teachers:teacher_create'))
        self.assertContains(form_response, 'Classes to teach')
        for school_class in school_classes:
            self.assertContains(form_response, school_class.name)

        response = self.client.post(reverse('teachers:teacher_create'), {
            'username': 'newteacher',
            'first_name': 'John',
            'last_name': 'Lado',
            'email': 'john@example.com',
            'phone': '+211900333444',
            'password': 'Teacher@12345',
            'staff_id': '',
            'department': department.pk,
            'assigned_classes': [school_class.pk for school_class in school_classes],
            'qualification': 'BSc Education',
            'specialization': 'Mathematics',
            'employment_type': 'full_time',
            'status': 'active',
            'date_joined': timezone.localdate().isoformat(),
            'office': 'Block A',
            'bio': 'Experienced mathematics educator',
        })
        self.assertRedirects(response, reverse('teachers:teacher_list'))
        user = User.objects.get(username='newteacher')
        self.assertEqual(user.role, User.Role.TEACHER)
        self.assertTrue(user.check_password('Teacher@12345'))
        self.assertIsInstance(user.teacher_profile, Teacher)
        self.assertSetEqual(
            set(user.teacher_profile.assigned_classes.all()), set(school_classes)
        )
        self.assertTrue(set(school_classes).issubset(set(teacher_classes(user))))

    def test_teacher_create_requires_at_least_one_class(self):
        self.login('admin')
        response = self.client.post(reverse('teachers:teacher_create'), {
            'username': 'unassignednewteacher',
            'first_name': 'New',
            'last_name': 'Teacher',
            'password': 'Teacher@12345',
            'staff_id': '',
            'qualification': 'BSc Education',
            'specialization': 'Mathematics',
            'employment_type': 'full_time',
            'status': 'active',
            'date_joined': timezone.localdate().isoformat(),
            'office': '',
            'bio': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('assigned_classes', response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='unassignednewteacher').exists())

    def test_parent_create_form_creates_linked_user(self):
        self.login('admin')
        response = self.client.post(reverse('students:parent_create'), {
            'username': 'newparent',
            'first_name': 'Mary',
            'last_name': 'Achol',
            'email': 'mary@example.com',
            'phone': '+211900555666',
            'password': 'Parent@12345',
            'occupation': 'Trader',
            'relationship': 'mother',
            'address': 'Juba',
            'alternate_phone': '+211900999000',
            'national_id': 'NAT-001122',
        })
        self.assertRedirects(response, reverse('students:parent_list'))
        user = User.objects.get(username='newparent')
        self.assertEqual(user.role, User.Role.PARENT)
        self.assertTrue(user.check_password('Parent@12345'))
        self.assertIsInstance(user.parent_profile, Parent)

    def test_landing_page_renders_for_guests_and_authenticated_users(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing/home.html')
        self.assertContains(response, 'Knowledge. Integrity.')
        self.assertContains(response, 'Admissions enquiries')
        self.assertContains(response, 'previous class or school results')
        self.assertContains(response, 'confirm any additional requirements')
        self.assertContains(response, 'Term dates')
        self.assertContains(response, 'Current curriculum subjects')
        self.assertContains(response, settings.SCHOOL_NAME)
        self.assertContains(response, settings.SCHOOL_ADDRESS)
        self.assertContains(response, settings.SCHOOL_PHONE_PRIMARY)
        self.assertContains(response, reverse('accounts:login'))
        self.assertContains(response, f'href="mailto:{settings.SCHOOL_EMAIL}"')
        self.assertContains(
            response,
            f'href="tel:{settings.SCHOOL_PHONE_PRIMARY.replace(" ", "")}"',
        )
        self.assertContains(
            response,
            f'href="tel:{settings.SCHOOL_PHONE_SECONDARY.replace(" ", "")}"',
        )
        self.assertNotContains(response, '1,248')
        self.assertNotContains(response, '86</strong>')
        self.assertNotContains(response, 'Live snapshot')

        admin = User.objects.get(username='admin')
        Announcement.objects.create(
            title='Public open day',
            message='Families may contact the school office for details.',
            audience=Announcement.Audience.ALL,
            is_published=True,
            is_public=True,
            created_by=admin,
        )
        Announcement.objects.create(
            title='Internal staff reminder',
            message='Staff-only information.',
            audience=Announcement.Audience.TEACHERS,
            is_published=True,
            is_public=False,
            created_by=admin,
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Public open day')
        self.assertNotContains(response, 'Internal staff reminder')

        self.login('admin')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('accounts:dashboard'))

    def test_landing_curriculum_lists_each_subject_name_once(self):
        academic_year = AcademicYear.objects.get(is_current=True)
        existing_subject = Subject.objects.filter(academic_year=academic_year).first()
        duplicate_subject = Subject.objects.create(
            name=existing_subject.name.upper(),
            code='DUPLICATE',
            academic_year=academic_year,
        )
        duplicate_subject.school_classes.set(existing_subject.school_classes.all())

        response = self.client.get(reverse('home'))
        subjects = response.context['curriculum_subjects']
        normalized_names = [name.casefold() for name in subjects]

        self.assertEqual(len(normalized_names), len(set(normalized_names)))
        self.assertEqual(normalized_names.count(existing_subject.name.casefold()), 1)

    def test_create_forms_require_visible_fields_but_not_generated_ids_or_files(self):
        self.login('admin')
        response = self.client.get(reverse('students:student_create'))
        form = response.context['form']
        required_fields = (
            'username', 'first_name', 'last_name', 'email', 'phone', 'password',
            'school_class', 'parent', 'admission_date', 'date_of_birth', 'gender',
            'department', 'term', 'status', 'address', 'guardian_name',
            'guardian_phone', 'blood_group',
            'medical_notes',
        )
        for name in required_fields:
            self.assertTrue(form.fields[name].required, name)
            if not isinstance(
                form.fields[name].widget, forms.CheckboxSelectMultiple
            ):
                self.assertIn('required', form.fields[name].widget.attrs, name)
        self.assertIn('student safety', form.fields['medical_notes'].help_text)
        self.assertFalse(form.fields['student_id'].required)

        response = self.client.get(reverse('accounts:user_create'))
        form = response.context['form']
        self.assertTrue(form.fields['password'].required)
        self.assertFalse(form.fields['photo'].required)
        self.assertFalse(form.fields['is_active'].required)

    def test_create_form_rejects_missing_required_fields(self):
        self.login('admin')
        response = self.client.post(reverse('students:student_create'), {
            'username': 'incomplete',
            'first_name': 'Incomplete',
            'last_name': 'Record',
            'password': 'Incomplete@12345',
        })
        self.assertEqual(response.status_code, 200)
        for name in ('email', 'phone', 'school_class', 'address', 'guardian_name'):
            self.assertIn(name, response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='incomplete').exists())

    def test_core_subjects_are_shared_by_arts_and_science(self):
        for school_class in SchoolClass.objects.filter(
            stream__in=[SchoolClass.Stream.ARTS, SchoolClass.Stream.SCIENCE]
        ):
            for code in ('MATH', 'ENG', 'ICT'):
                subject = Subject.objects.get(
                    code=code, school_classes=school_class
                )
                self.assertEqual(
                    set(subject.departments.values_list('code', flat=True)),
                    {'ART', 'SCI'},
                    f'{code} in {school_class.name}',
                )
                self.assertTrue(subject.is_dual_department)

        mathematics = Subject.objects.filter(code='MATH').first()
        biology = Subject.objects.filter(code='BIO').first()
        geography = Subject.objects.filter(code='GEO').first()
        self.assertEqual(mathematics.department_names, 'Arts, Science')
        self.assertEqual(
            set(biology.departments.values_list('code', flat=True)), {'SCI'}
        )
        self.assertEqual(
            set(geography.departments.values_list('code', flat=True)), {'ART'}
        )
        self.assertFalse(biology.is_dual_department)

    def test_subject_form_allows_multiple_classes_like_departments(self):
        year = AcademicYear.objects.get(name='2026')
        arts_class = SchoolClass.objects.get(name='Senior 3 Arts', academic_year=year)
        science_class = SchoolClass.objects.get(
            name='Senior 3 Science', academic_year=year
        )
        departments = list(Department.objects.filter(code__in=['ART', 'SCI']))
        teacher = User.objects.get(username='teacher1')
        term = Term.objects.filter(academic_year=year).first()
        form = SubjectForm(data={
            'name': 'Core Skills',
            'code': 'COREX',
            'departments': [department.pk for department in departments],
            'school_classes': [arts_class.pk, science_class.pk],
            'teacher': teacher.pk,
            'academic_year': year.pk,
            'term': term.name,
            'is_active': 'on',
            'description': '',
        })

        self.assertEqual(
            type(form.fields['school_classes'].widget),
            type(form.fields['departments'].widget),
        )
        self.assertTrue(form.is_valid(), form.errors)
        subject = form.save()
        self.assertSetEqual(
            set(subject.school_classes.all()), {arts_class, science_class}
        )

    def test_subject_and_student_forms_use_fixed_term_choices(self):
        expected = list(Term.Name.choices)
        subject_form = SubjectForm()
        student_form = StudentForm()
        term_form = TermForm()
        enrollment_form = EnrollmentForm()
        examination_form = ExaminationForm()
        fee_form = FeeForm()
        self.assertEqual(
            [
                choice for choice in subject_form.fields['term'].choices
                if choice[0]
            ],
            expected,
        )
        self.assertEqual(list(student_form.fields['term'].choices), expected)
        self.assertEqual(
            type(student_form.fields['term'].widget),
            type(subject_form.fields['school_classes'].widget),
        )
        for form, field_name in (
            (term_form, 'name'),
            (subject_form, 'term'),
            (enrollment_form, 'term'),
            (examination_form, 'term'),
            (fee_form, 'term'),
        ):
            self.assertIsInstance(form.fields[field_name].widget, forms.RadioSelect)
        self.assertEqual(
            [
                choice for choice in fee_form.fields['term'].choices
                if choice[0]
            ],
            list(Term.Name.choices),
        )

    def test_student_portal_displays_class_and_department(self):
        user = self.login('student1')
        student = user.student_profile
        response = self.client.get(reverse('accounts:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Class: {student.school_class.name}')
        self.assertContains(response, f'Department: {student.department.name}')

    def test_seed_creates_three_terms_within_the_academic_year(self):
        year = AcademicYear.objects.get(name='2026')
        terms = Term.objects.filter(academic_year=year)
        self.assertEqual(terms.count(), 3)
        self.assertEqual(
            set(terms.values_list('name', flat=True)),
            {'Term 1', 'Term 2', 'Term 3'},
        )
        self.assertEqual(terms.filter(is_current=True).count(), 1)
        for term in terms:
            self.assertGreaterEqual(term.start_date, year.start_date)
            self.assertLessEqual(term.end_date, year.end_date)

    def test_academic_year_form_adds_term_dates(self):
        self.login('admin')
        response = self.client.get(reverse('academics:year_create'))
        self.assertEqual(response.status_code, 200)
        for field in (
            'term_1_start_date', 'term_1_end_date',
            'term_2_start_date', 'term_2_end_date',
            'term_3_start_date', 'term_3_end_date',
        ):
            self.assertContains(response, f'name="{field}"')
            self.assertFalse(response.context['form'].fields[field].required)

        year_list = self.client.get(reverse('academics:year_list'))
        self.assertContains(year_list, 'Manage Term Dates')
        self.assertContains(year_list, reverse('academics:term_list'))

        response = self.client.post(reverse('academics:year_create'), {
            'name': '2027',
            'start_date': '2027-01-01',
            'end_date': '2027-12-31',
            'term_1_start_date': '2027-01-10',
            'term_1_end_date': '2027-04-15',
            'term_2_start_date': '2027-05-01',
            'term_2_end_date': '2027-08-15',
            'term_3_start_date': '2027-09-01',
            'term_3_end_date': '2027-11-30',
        })

        self.assertRedirects(response, reverse('academics:year_list'))
        year = AcademicYear.objects.get(name='2027')
        terms = {
            term.name: (term.start_date.isoformat(), term.end_date.isoformat())
            for term in Term.objects.filter(academic_year=year)
        }
        self.assertEqual(terms, {
            'Term 1': ('2027-01-10', '2027-04-15'),
            'Term 2': ('2027-05-01', '2027-08-15'),
            'Term 3': ('2027-09-01', '2027-11-30'),
        })

    def test_academic_year_form_validates_term_date_pairs_and_year_bounds(self):
        self.login('admin')
        incomplete = self.client.post(reverse('academics:year_create'), {
            'name': '2027',
            'start_date': '2027-01-01',
            'end_date': '2027-12-31',
            'term_1_start_date': '2027-01-10',
            'term_1_end_date': '',
        })
        self.assertEqual(incomplete.status_code, 200)
        self.assertIn('term_1_end_date', incomplete.context['form'].errors)

        outside_year = self.client.post(reverse('academics:year_create'), {
            'name': '2027',
            'start_date': '2027-01-01',
            'end_date': '2027-12-31',
            'term_1_start_date': '2026-12-20',
            'term_1_end_date': '2027-01-10',
        })
        self.assertEqual(outside_year.status_code, 200)
        self.assertIn('term_1_start_date', outside_year.context['form'].errors)

    def test_academic_year_edit_prefills_and_updates_term_dates(self):
        self.login('admin')
        year = AcademicYear.objects.get(name='2026')
        term = Term.objects.get(academic_year=year, name=Term.Name.TERM_1)
        response = self.client.get(reverse('academics:year_update', args=[year.pk]))
        self.assertEqual(response.context['form']['term_1_start_date'].value(), term.start_date)

        response = self.client.post(
            reverse('academics:year_update', args=[year.pk]),
            {
                'name': year.name,
                'start_date': year.start_date.isoformat(),
                'end_date': year.end_date.isoformat(),
                'term_1_start_date': '2026-02-03',
                'term_1_end_date': '2026-05-08',
                'term_2_start_date': '2026-05-25',
                'term_2_end_date': '2026-08-21',
                'term_3_start_date': '2026-09-07',
                'term_3_end_date': '2026-11-27',
            },
        )

        self.assertRedirects(response, reverse('academics:year_list'))
        term.refresh_from_db()
        self.assertEqual(term.start_date.isoformat(), '2026-02-03')

    def test_term_validation_rejects_invalid_dates_and_a_fourth_term(self):
        year = AcademicYear.objects.get(name='2026')
        invalid_dates = Term(
            name=Term.Name.TERM_1,
            academic_year=year,
            start_date=year.start_date - timedelta(days=1),
            end_date=year.start_date + timedelta(days=30),
        )
        with self.assertRaises(ValidationError):
            invalid_dates.full_clean()

        fourth_term = Term(
            name=Term.Name.TERM_1,
            academic_year=year,
            start_date=year.start_date,
            end_date=year.start_date + timedelta(days=30),
        )
        with self.assertRaisesMessage(ValidationError, 'at most three terms'):
            fourth_term.full_clean()

    def test_streamed_and_unstreamed_classes_are_configured_correctly(self):
        classes = SchoolClass.objects.filter(academic_year__name='2026')
        self.assertEqual(classes.count(), 6)
        self.assertFalse(
            classes.filter(
                level__in=[SchoolClass.Level.SENIOR_1, SchoolClass.Level.SENIOR_2]
            ).exclude(stream='', department__isnull=True).exists()
        )
        for school_class in classes.filter(
            level__in=[SchoolClass.Level.SENIOR_3, SchoolClass.Level.SENIOR_4]
        ):
            self.assertIn(school_class.stream, SchoolClass.Stream.values)
            self.assertIsNotNone(school_class.department)

        arts_codes = set(
            Subject.objects.filter(
                school_classes__name='Senior 3 Arts'
            ).values_list('code', flat=True)
        )
        science_codes = set(
            Subject.objects.filter(
                school_classes__name='Senior 3 Science'
            ).values_list('code', flat=True)
        )
        shared_codes = {'MATH', 'ENG', 'ICT'}
        self.assertTrue(shared_codes.issubset(arts_codes))
        self.assertTrue(shared_codes.issubset(science_codes))
        self.assertIn('GEO', arts_codes)
        self.assertNotIn('BIO', arts_codes)
        self.assertIn('BIO', science_codes)
        self.assertNotIn('GEO', science_codes)

    def test_senior_classes_have_differentiated_tuition_fees(self):
        tuition = {
            fee.school_class.name: fee.amount
            for fee in Fee.objects.filter(name='Tuition Fee')
        }
        self.assertEqual(tuition['Senior 1 A'], Decimal('75000.00'))
        self.assertEqual(tuition['Senior 2 A'], Decimal('75000.00'))
        self.assertEqual(tuition['Senior 3 Arts'], Decimal('85000.00'))
        self.assertEqual(tuition['Senior 3 Science'], Decimal('95000.00'))
        self.assertEqual(tuition['Senior 4 Arts'], Decimal('90000.00'))
        self.assertEqual(tuition['Senior 4 Science'], Decimal('100000.00'))

    def test_school_class_create_allows_unstreamed_classes(self):
        self.login('admin')
        year = AcademicYear.objects.get(name='2026')
        response = self.client.post(reverse('academics:class_create'), {
            'name': 'Senior 1 B',
            'level': SchoolClass.Level.SENIOR_1,
            'stream': '',
            'department': '',
            'academic_year': year.pk,
            'class_teacher': '',
            'capacity': '40',
            'room': 'Room 5',
        })
        self.assertRedirects(response, reverse('academics:class_list'))
        self.assertTrue(SchoolClass.objects.filter(name='Senior 1 B').exists())

    def test_school_class_create_requires_stream_for_senior_three(self):
        self.login('admin')
        year = AcademicYear.objects.get(name='2026')
        response = self.client.post(reverse('academics:class_create'), {
            'name': 'Senior 3 Invalid',
            'level': SchoolClass.Level.SENIOR_3,
            'stream': '',
            'department': '',
            'academic_year': year.pk,
            'class_teacher': '',
            'capacity': '40',
            'room': 'Room 9',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('stream', response.context['form'].errors)
        self.assertFalse(SchoolClass.objects.filter(name='Senior 3 Invalid').exists())

    def test_legal_pages_render(self):
        route_names = [
            'privacy_policy', 'terms_of_service', 'cookie_policy',
            'acceptable_use', 'data_protection', 'child_protection',
        ]
        for name in route_names:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertTemplateUsed(response, f'legal/{name}.html')

    def test_registration_fee_applies_to_every_student(self):
        registration_fee = Fee.objects.get(
            name='Registration Fee', school_class=None
        )
        self.assertTrue(registration_fee.applies_to_all_classes)
        self.assertEqual(registration_fee.class_scope, 'All classes')
        for student in Student.objects.all():
            self.assertIn(
                registration_fee, active_fees_for_student(student), student.student_id
            )

        user = self.login('student1')
        response = self.client.get(
            reverse('finance:fee_statement', args=[user.student_profile.pk])
        )
        self.assertContains(response, 'Registration Fee')

    def test_fee_create_accepts_universal_fee_without_class(self):
        self.login('accountant')
        form_response = self.client.get(reverse('finance:fee_create'))
        self.assertContains(form_response, 'Term 1')
        self.assertContains(form_response, 'Term 2')
        self.assertContains(form_response, 'Term 3')

        existing_fee = Fee.objects.first()
        year = existing_fee.academic_year
        response = self.client.post(reverse('finance:fee_create'), {
            'name': 'Library Fund',
            'school_class': '',
            'academic_year': year.pk,
            'term': existing_fee.term,
            'amount': '15000.00',
            'due_date': timezone.localdate().isoformat(),
            'is_active': 'on',
            'description': 'Universal library contribution.',
        })
        self.assertRedirects(response, reverse('finance:fee_list'))
        fee = Fee.objects.get(name='Library Fund', academic_year=year)
        self.assertIsNone(fee.school_class)

    def test_unassigned_teacher_cannot_view_students(self):
        user = User.objects.create_user(
            username='unassignedteacher',
            password='Teacher@12345',
            role=User.Role.TEACHER,
            first_name='Unassigned',
            last_name='Teacher',
        )
        Teacher.objects.create(
            user=user,
            staff_id='GSS-T-TEST-999',
            department=Department.objects.first(),
        )
        self.client.force_login(user)
        student = Student.objects.first()

        response = self.client.get(reverse('students:student_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)

        response = self.client.get(
            reverse('students:student_detail', args=[student.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_view_students_in_assigned_classes(self):
        user = self.login('teacher1')
        school_class = teacher_classes(user).first()
        student = Student.objects.filter(school_class=school_class).first()
        response = self.client.get(
            reverse('students:student_detail', args=[student.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_student_can_download_own_report_card_only(self):
        user = self.login('student1')
        student = user.student_profile
        exam = Examination.objects.filter(school_class=student.school_class).first()
        other = Student.objects.exclude(pk=student.pk).first()

        response = self.client.get(
            reverse('examinations:report_card_pdf', args=[student.pk, exam.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        response = self.client.get(
            reverse('examinations:report_card_pdf', args=[other.pk, exam.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_student_dashboard_lists_report_card_downloads(self):
        user = self.login('student1')
        student = user.student_profile
        exam = Examination.objects.filter(school_class=student.school_class).first()
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(response, 'My Report Cards')
        self.assertContains(
            response,
            reverse('examinations:report_card_pdf', args=[student.pk, exam.pk]),
        )

    def test_report_exports_and_pdf_documents_render(self):
        self.login('admin')
        exports = [
            'export_students',
            'export_teachers',
            'export_attendance',
            'export_results',
            'export_finance',
        ]
        for name in exports:
            for fmt in ('excel', 'pdf'):
                response = self.client.get(reverse(f'reports:{name}', args=[fmt]))
                self.assertEqual(response.status_code, 200, f'{name}:{fmt}')

        student = Student.objects.first()
        exam = Examination.objects.first()
        payment = Payment.objects.first()
        response = self.client.get(
            reverse('examinations:report_card_pdf', args=[student.pk, exam.pk])
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('finance:receipt_pdf', args=[payment.pk]))
        self.assertEqual(response.status_code, 200)
