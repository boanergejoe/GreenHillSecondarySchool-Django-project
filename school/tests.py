from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academics.access import teacher_classes
from academics.models import AcademicYear, Department, SchoolClass, Subject, Term
from accounts.models import User
from assignments.models import Assignment
from examinations.models import Examination
from finance.models import Fee, Payment
from finance.services import active_fees_for_student
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
            subject__school_class=student.school_class
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
            subject__school_class=student.school_class
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

    def test_student_create_form_creates_linked_user(self):
        self.login('admin')
        school_class = SchoolClass.objects.first()
        parent = Parent.objects.first()
        response = self.client.post(reverse('students:student_create'), {
            'username': 'newstudent',
            'first_name': 'Amina',
            'last_name': 'Kiden',
            'email': 'amina@example.com',
            'phone': '+211900111222',
            'password': 'Student@12345',
            'student_id': '',
            'school_class': school_class.pk,
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

    def test_teacher_create_form_creates_linked_user(self):
        self.login('admin')
        department = Department.objects.first()
        response = self.client.post(reverse('teachers:teacher_create'), {
            'username': 'newteacher',
            'first_name': 'John',
            'last_name': 'Lado',
            'email': 'john@example.com',
            'phone': '+211900333444',
            'password': 'Teacher@12345',
            'staff_id': '',
            'department': department.pk,
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
        self.assertContains(response, 'Smarter School Management.')
        self.assertContains(response, settings.SCHOOL_NAME)
        self.assertContains(response, settings.SCHOOL_ADDRESS)
        self.assertContains(response, settings.SCHOOL_PHONE_PRIMARY)
        self.assertContains(response, reverse('accounts:login'))

        self.login('admin')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('accounts:dashboard'))

    def test_create_forms_require_visible_fields_but_not_generated_ids_or_files(self):
        self.login('admin')
        response = self.client.get(reverse('students:student_create'))
        form = response.context['form']
        required_fields = (
            'username', 'first_name', 'last_name', 'email', 'phone', 'password',
            'school_class', 'parent', 'admission_date', 'date_of_birth', 'gender',
            'status', 'address', 'guardian_name', 'guardian_phone', 'blood_group',
            'medical_notes',
        )
        for name in required_fields:
            self.assertTrue(form.fields[name].required, name)
            self.assertIn('required', form.fields[name].widget.attrs, name)
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
                    code=code, school_class=school_class
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
                school_class__name='Senior 3 Arts'
            ).values_list('code', flat=True)
        )
        science_codes = set(
            Subject.objects.filter(
                school_class__name='Senior 3 Science'
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
        existing_fee = Fee.objects.first()
        year = existing_fee.academic_year
        response = self.client.post(reverse('finance:fee_create'), {
            'name': 'Library Fund',
            'school_class': '',
            'academic_year': year.pk,
            'term': existing_fee.term_id,
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
