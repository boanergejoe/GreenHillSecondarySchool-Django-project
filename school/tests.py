import json
from io import BytesIO, StringIO
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.conf import settings
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academics.access import teacher_classes, teacher_subjects
from academics.forms import EnrollmentForm, SubjectForm, TermForm
from academics.models import (
    AcademicAuditLog, AcademicYear, Department, Enrollment, LessonPlan,
    ExaminationSession, SchoolClass, Subject, SyllabusCoverage,
    TeacherAttendance, TeachingObservation, TeachingSchedule, Term,
)
from accounts.models import User
from assignments.models import Assignment, Quiz, QuizAttempt, QuizQuestion
from attendance.models import Attendance
from communications.models import Announcement
from examinations.forms import ExaminationForm
from examinations.models import Examination, Result
from finance.forms import FeeForm, PaymentForm
from finance.models import Fee, Payment
from finance.services import (
    active_fees_for_student, exam_eligibility_for_student, fee_totals_for_student,
)
from students.forms import StudentForm
from students.models import Parent, ReadmissionRequest, Student
from teachers.models import Teacher


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
)
class GreenHillSecondaryIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', verbosity=0)
        User.objects.create_user(
            username='dos_test',
            password='Dos@12345',
            first_name='Director',
            last_name='of Studies',
            role=User.Role.DOS,
        )

    def login(self, username):
        user = User.objects.get(username=username)
        self.client.force_login(user)
        return user

    def test_all_role_dashboards_render(self):
        for username in (
            'admin', 'teacher1', 'student1', 'parent1', 'accountant',
            'registrar', 'dos_test',
        ):
            self.login(username)
            response = self.client.get(reverse('accounts:dashboard'))
            self.assertEqual(response.status_code, 200, username)
            if username == 'registrar':
                self.assertEqual(response.context['dashboard_type'], 'registrar')
            elif username == 'dos_test':
                self.assertEqual(response.context['dashboard_type'], 'dos')

    def test_dos_can_manage_academic_pages_but_not_finance_or_student_records(self):
        self.login('dos_test')
        urls = [
            reverse('academics:department_list'),
            reverse('academics:year_list'),
            reverse('academics:term_list'),
            reverse('academics:class_list'),
            reverse('academics:subject_list'),
            reverse('academics:enrollment_list'),
            reverse('academics:syllabus_coverage_list'),
            reverse('academics:syllabus_coverage_create'),
            reverse('academics:lesson_plan_list'),
            reverse('academics:lesson_plan_create'),
            reverse('academics:observation_list'),
            reverse('academics:observation_create'),
            reverse('academics:teacher_attendance_list'),
            reverse('academics:teacher_attendance_create'),
            reverse('academics:academic_activity'),
            reverse('academics:academic_notice_create'),
            reverse('academics:teaching_schedule_list'),
            reverse('academics:teaching_schedule_create'),
            reverse('academics:examination_session_list'),
            reverse('academics:examination_session_create'),
            reverse('examinations:exam_list'),
            reverse('examinations:exam_create'),
            reverse('examinations:result_list'),
            reverse('attendance:list'),
            reverse('reports:index'),
            reverse('reports:export_results', args=['excel']),
            reverse('reports:class_performance'),
            reverse('reports:teacher_performance'),
            reverse('reports:subject_performance'),
            reverse('reports:department_performance'),
            reverse('reports:syllabus_coverage'),
            reverse('reports:student_progress'),
            reverse('teachers:teacher_list'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200, url)

        for url in (
            reverse('students:student_list'),
            reverse('finance:financial_overview'),
            reverse('finance:payment_list'),
            reverse(
                'examinations:enter_results',
                args=[Examination.objects.first().pk],
            ),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_future_student_birth_dates_are_rejected(self):
        future_date = timezone.localdate() + timedelta(days=1)
        form = StudentForm(data={'date_of_birth': future_date.isoformat()})
        self.assertFalse(form.is_valid())
        self.assertIn('date_of_birth', form.errors)

        student_user = User.objects.create_user(
            username='future_dob_test',
            password='Student@12345',
            role=User.Role.STUDENT,
        )
        student = Student(user=student_user, date_of_birth=future_date)
        self.assertIsNone(student.age)
        with self.assertRaises(ValidationError):
            student.full_clean()
        with self.assertRaises(ValidationError):
            student.save()

    def test_teacher_can_submit_lesson_plan_and_syllabus_coverage(self):
        teacher = self.login('teacher1')
        subject = teacher_subjects(teacher).first()
        self.assertIsNotNone(subject)
        school_class = subject.school_classes.first()
        self.assertIsNotNone(school_class)
        year = school_class.academic_year

        response = self.client.post(reverse('academics:lesson_plan_create'), {
            'academic_year': year.pk,
            'term': Term.Name.TERM_1,
            'school_class': school_class.pk,
            'subject': subject.pk,
            'lesson_date': timezone.localdate().isoformat(),
            'topic': 'Linear equations',
            'objectives': 'Solve simple linear equations.',
            'resources': 'Textbook and board',
        })
        self.assertRedirects(response, reverse('academics:lesson_plan_list'))
        lesson_plan = LessonPlan.objects.get(topic='Linear equations')
        self.assertEqual(lesson_plan.teacher, teacher)
        self.assertTrue(
            AcademicAuditLog.objects.filter(
                action='lesson_plan_submitted',
                object_id=str(lesson_plan.pk),
            ).exists()
        )

        response = self.client.post(
            reverse('academics:syllabus_coverage_create'),
            {
                'academic_year': year.pk,
                'term': Term.Name.TERM_1,
                'school_class': school_class.pk,
                'subject': subject.pk,
                'topics_planned': 12,
                'topics_completed': 5,
                'notes': 'Unit 1 complete.',
            },
        )
        self.assertRedirects(
            response, reverse('academics:syllabus_coverage_list')
        )
        coverage = SyllabusCoverage.objects.get(
            academic_year=year,
            term=Term.Name.TERM_1,
            school_class=school_class,
            subject=subject,
        )
        self.assertEqual(coverage.completion_percentage, 41.7)
        self.assertEqual(coverage.updated_by, teacher)

    def test_dos_can_review_lesson_plans_and_record_observations(self):
        teacher = User.objects.get(username='teacher1')
        subject = teacher_subjects(teacher).first()
        school_class = subject.school_classes.first()
        year = school_class.academic_year
        lesson_plan = LessonPlan.objects.create(
            academic_year=year,
            term=Term.Name.TERM_1,
            school_class=school_class,
            subject=subject,
            teacher=teacher,
            lesson_date=timezone.localdate(),
            topic='Fractions',
            objectives='Compare fractions.',
        )
        dos = self.login('dos_test')
        response = self.client.post(
            reverse('academics:lesson_plan_review', args=[lesson_plan.pk]),
            {'status': LessonPlan.Status.REVISION, 'review_note': 'Add examples.'},
        )
        self.assertRedirects(response, reverse('academics:lesson_plan_list'))
        lesson_plan.refresh_from_db()
        self.assertEqual(lesson_plan.status, LessonPlan.Status.REVISION)
        self.assertEqual(lesson_plan.reviewed_by, dos)
        self.assertTrue(teacher.notifications.filter(
            title='Lesson plan revision requested'
        ).exists())

        response = self.client.post(reverse('academics:observation_create'), {
            'teacher': teacher.pk,
            'school_class': school_class.pk,
            'subject': subject.pk,
            'observed_on': timezone.localdate().isoformat(),
            'lesson_prepared': 'on',
            'rating': 4,
            'strengths': 'Clear objectives and student participation.',
            'improvement_areas': 'Use more formative checks.',
            'recommendation': 'Add an exit ticket.',
        })
        self.assertRedirects(response, reverse('academics:observation_list'))
        observation = TeachingObservation.objects.get(observer=dos)
        self.assertEqual(observation.rating, 4)
        self.assertTrue(AcademicAuditLog.objects.filter(
            action='teaching_observation_recorded',
            object_id=str(observation.pk),
        ).exists())

        response = self.client.post(
            reverse('academics:teacher_attendance_create'),
            {
                'teacher': teacher.pk,
                'date': timezone.localdate().isoformat(),
                'status': TeacherAttendance.Status.PRESENT,
                'check_in': '07:45',
                'check_out': '15:00',
                'note': 'On time.',
            },
        )
        self.assertRedirects(
            response, reverse('academics:teacher_attendance_list')
        )
        attendance = TeacherAttendance.objects.get(teacher=teacher)
        self.assertEqual(attendance.recorded_by, dos)
        self.assertEqual(attendance.status, TeacherAttendance.Status.PRESENT)
        self.assertTrue(AcademicAuditLog.objects.filter(
            action='academic_record_created',
            object_id=str(attendance.pk),
            object_type='TeacherAttendance',
        ).exists())

    def test_dos_department_notice_is_only_sent_to_that_department(self):
        teacher = User.objects.get(username='teacher1')
        department = teacher.teacher_profile.department
        self.assertIsNotNone(department)
        self.login('dos_test')
        response = self.client.post(reverse('academics:academic_notice_create'), {
            'title': 'Department meeting',
            'message': 'Please submit department reports.',
            'recipient': 'department',
            'department': department.pk,
        })
        self.assertRedirects(response, reverse('academics:academic_activity'))
        self.assertTrue(teacher.notifications.filter(
            title='Department meeting'
        ).exists())
        expected_recipients = set(User.objects.filter(
            role=User.Role.TEACHER,
            teacher_profile__department=department,
        ).values_list('pk', flat=True))
        actual_recipients = set(User.objects.filter(
            notifications__title='Department meeting'
        ).values_list('pk', flat=True))
        self.assertSetEqual(actual_recipients, expected_recipients)
        self.assertFalse(Announcement.objects.filter(
            title='Department meeting'
        ).exists())

    def test_dos_academic_reports_support_pdf_and_excel(self):
        self.login('dos_test')
        for route_name in (
            'reports:teacher_performance',
            'reports:subject_performance',
            'reports:department_performance',
            'reports:syllabus_coverage',
            'reports:student_progress',
        ):
            for output_format, content_type in (
                ('excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('pdf', 'application/pdf'),
            ):
                with self.subTest(route=route_name, format=output_format):
                    response = self.client.get(
                        reverse(route_name), {'format': output_format}
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['Content-Type'], content_type)

    def test_dos_can_schedule_classes_and_examination_invigilators(self):
        dos = self.login('dos_test')
        teacher = User.objects.get(username='teacher1')
        subject = teacher_subjects(teacher).first()
        school_class = subject.school_classes.first()
        year = school_class.academic_year

        schedule_data = {
            'academic_year': year.pk,
            'term': Term.Name.TERM_1,
            'school_class': school_class.pk,
            'subject': subject.pk,
            'teacher': teacher.pk,
            'weekday': TeachingSchedule.Weekday.MONDAY,
            'start_time': '08:00',
            'end_time': '08:45',
            'room': 'Room 1',
        }
        response = self.client.post(
            reverse('academics:teaching_schedule_create'), schedule_data
        )
        self.assertRedirects(
            response, reverse('academics:teaching_schedule_list')
        )
        schedule = TeachingSchedule.objects.get(room='Room 1')
        self.assertEqual(schedule.teacher, teacher)
        self.assertTrue(AcademicAuditLog.objects.filter(
            action='academic_record_created',
            object_id=str(schedule.pk),
            object_type='TeachingSchedule',
        ).exists())

        exam = Examination.objects.filter(academic_year=year).first()
        self.assertIsNotNone(exam)
        exam.school_classes.add(school_class)
        session_data = {
            'examination': exam.pk,
            'school_class': school_class.pk,
            'subject': subject.pk,
            'exam_date': exam.start_date.isoformat(),
            'start_time': '09:00',
            'end_time': '10:00',
            'venue': 'Main Hall',
            'invigilators': [teacher.pk],
        }
        response = self.client.post(
            reverse('academics:examination_session_create'), session_data
        )
        self.assertRedirects(
            response, reverse('academics:examination_session_list')
        )
        session = ExaminationSession.objects.get(examination=exam)
        self.assertEqual(session.created_by, dos)
        self.assertSetEqual(set(session.invigilators.all()), {teacher})
        self.assertTrue(teacher.notifications.filter(
            title=f'Examination duty: {exam.name}'
        ).exists())

    def test_excel_exports_write_formula_like_user_values_as_text(self):
        from reports import views as report_views

        if report_views.Workbook is None:
            self.skipTest('openpyxl is required for Excel exports.')

        from openpyxl import load_workbook

        formula_like_values = [
            ' \t=1+1',
            '\x01+1',
            '-1',
            '@SUM(1,1)',
        ]
        response = report_views._excel_response(
            'formula-safety',
            ['Value'],
            [[value] for value in formula_like_values],
            'Safety',
        )
        workbook = load_workbook(BytesIO(response.content), data_only=False)
        for row_number, original_value in enumerate(formula_like_values, start=2):
            with self.subTest(value=repr(original_value)):
                cell = workbook.active.cell(row=row_number, column=1)
                self.assertEqual(cell.data_type, 's')
                self.assertTrue(cell.value.startswith("'"))
        self.assertEqual(workbook.active['A2'].value, "' \t=1+1")
        self.assertEqual(workbook.active['A3'].value, "'+1")

    def test_registrar_dashboard_displays_student_records_and_actions(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'registrar', 'password': 'Registrar@12345'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dashboard_type'], 'registrar')
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertContains(response, 'Admissions and records')
        self.assertContains(response, reverse('students:student_create'))
        self.assertContains(response, reverse('students:archived_students'))
        self.assertContains(response, reverse('students:student_list'))

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
        exam = Examination.objects.filter(school_classes=student.school_class).first()
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
        exam = Examination.objects.filter(school_classes=student.school_class).first()
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
        fee = Fee.objects.create(
            name='Workflow payment fee',
            school_class=student.school_class,
            academic_year=student.school_class.academic_year,
            amount=Decimal('5000.00'),
        )
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

    def test_payment_form_supplies_only_student_applicable_fee_data(self):
        self.login('accountant')
        student = Parent.objects.get(
            user__username='parent1'
        ).children.select_related('school_class').first()
        response = self.client.get(reverse('finance:payment_create'))
        self.assertEqual(response.status_code, 200)
        student_data = response.context['payment_auto_fill_data'][str(student.pk)]
        self.assertEqual(student_data['class_name'], student.school_class.name)
        self.assertEqual(
            student_data['academic_year'],
            student.school_class.academic_year.name,
        )
        self.assertEqual(
            {int(item['id']) for item in student_data['fees']},
            set(active_fees_for_student(student).values_list('pk', flat=True)),
        )
        self.assertContains(response, 'payment-auto-fill-data')

    def test_payment_form_rejects_wrong_class_fees_and_overpayment(self):
        student = Student.objects.exclude(school_class__isnull=True).first()
        fee = Fee.objects.create(
            name='Payment validation fee',
            school_class=student.school_class,
            academic_year=student.school_class.academic_year,
            amount=Decimal('100.00'),
        )
        data = {
            'student': student.pk,
            'fee': fee.pk,
            'amount': '101.00',
            'payment_date': timezone.localdate().isoformat(),
            'method': Payment.Method.CASH,
        }
        form = PaymentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

        other_student = Student.objects.exclude(
            school_class_id=student.school_class_id
        ).exclude(school_class__isnull=True).first()
        self.assertIsNotNone(other_student)
        data.update({'student': other_student.pk, 'amount': '1.00'})
        form = PaymentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('fee', form.errors)

    def test_results_are_hidden_until_teacher_entry_is_published(self):
        teacher = self.login('teacher1')
        exam = Examination.objects.filter(
            school_classes__in=teacher_classes(teacher)
        ).first()
        self.assertIsNotNone(exam)
        school_class = exam.school_classes.filter(
            pk__in=teacher_classes(teacher)
        ).first()
        self.assertIsNotNone(school_class)
        student = Student.objects.filter(
            school_class=school_class,
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
                'term': exam.term,
                'school_classes': list(
                    exam.school_classes.values_list('pk', flat=True)
                ),
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
        if school_class.level in (SchoolClass.Level.SENIOR_1, SchoolClass.Level.SENIOR_2):
            self.assertIsNone(user.student_profile.department)
        else:
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
        self.assertContains(response, 'Nobility. Honor.')
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

    def test_public_language_switch_translates_content_and_sets_arabic_direction(self):
        response = self.client.post(reverse('set_language'), {
            'language': 'fr',
            'next': '/',
        })
        self.assertEqual(response.status_code, 302)
        french = self.client.get(reverse('home'))
        self.assertContains(french, 'Accueil')
        self.assertContains(french, 'Noblesse. Honneur. Excellence.')

        self.client.post(reverse('set_language'), {
            'language': 'ar',
            'next': '/',
        })
        arabic = self.client.get(reverse('home'))
        self.assertContains(arabic, 'الرئيسية')
        self.assertContains(arabic, 'dir="rtl"')

        self.client.post(reverse('set_language'), {
            'language': 'fr',
            'next': '/',
        })
        self.login('teacher1')
        portal = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(portal, 'Mes matières')

    def test_create_forms_require_visible_fields_but_not_generated_ids_or_files(self):
        self.login('admin')
        response = self.client.get(reverse('students:student_create'))
        form = response.context['form']
        self.assertContains(response, 'data-department-field')
        self.assertContains(response, 'data-level="Senior 1"')
        required_fields = (
            'username', 'first_name', 'last_name', 'email', 'phone', 'password',
            'school_class', 'parent', 'admission_date', 'date_of_birth', 'gender',
            'term', 'status', 'address', 'guardian_name',
            'guardian_phone', 'blood_group',
            'medical_notes',
        )
        for name in required_fields:
            self.assertTrue(form.fields[name].required, name)
            if not isinstance(
                form.fields[name].widget, forms.CheckboxSelectMultiple
            ):
                self.assertIn('required', form.fields[name].widget.attrs, name)
        self.assertFalse(form.fields['department'].required)
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
        self.assertIsInstance(
            examination_form.fields['school_classes'].widget,
            forms.CheckboxSelectMultiple,
        )
        self.assertEqual(
            [
                choice for choice in examination_form.fields['term'].choices
                if choice[0]
            ],
            expected,
        )
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

    def test_examination_term_choices_work_without_database_term_rows(self):
        self.login('admin')
        year = AcademicYear.objects.get(name='2026')
        school_classes = list(
            SchoolClass.objects.filter(academic_year=year)[:2]
        )
        self.assertEqual(len(school_classes), 2)
        Term.objects.filter(academic_year=year).delete()

        response = self.client.get(reverse('examinations:exam_create'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].fields['school_classes'].required)
        term_choices = [
            choice for choice in response.context['form'].fields['term'].choices
            if choice[0]
        ]
        self.assertEqual(term_choices, list(Term.Name.choices))
        admin_response = self.client.get(
            reverse('admin:examinations_examination_add')
        )
        self.assertEqual(admin_response.status_code, 200)
        for _, label in Term.Name.choices:
            self.assertContains(admin_response, label)

        response = self.client.post(reverse('examinations:exam_create'), {
            'name': 'Term 3 Exams Without Calendar Rows',
            'exam_type': Examination.ExamType.FINAL,
            'academic_year': year.pk,
            'term': Term.Name.TERM_3,
            'school_classes': [item.pk for item in school_classes],
            'start_date': '2026-10-12',
            'end_date': '2026-10-20',
            'total_marks': 100,
        })

        self.assertRedirects(response, reverse('examinations:exam_list'))
        exam = Examination.objects.get(name='Term 3 Exams Without Calendar Rows')
        self.assertEqual(exam.term, Term.Name.TERM_3)
        self.assertSetEqual(
            set(exam.school_classes.all()), set(school_classes)
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
        exam = Examination.objects.filter(school_classes=student.school_class).first()
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
        exam = Examination.objects.filter(school_classes=student.school_class).first()
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(response, 'My Report Cards')
        self.assertContains(
            response,
            reverse('examinations:report_card_pdf', args=[student.pk, exam.pk]),
        )

    def test_student_dashboard_offers_re_admission_request(self):
        self.login('student1')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(response, 'Re-admission')
        self.assertContains(
            response, reverse('students:readmission_request')
        )

    def test_student_can_request_re_admission_without_changing_enrollment(self):
        student = User.objects.get(username='student1').student_profile
        previous_class = student.school_class
        self.login('student1')
        response = self.client.post(
            reverse('students:readmission_request'),
            {
                'school_class': previous_class.pk,
                'terms': [Term.Name.TERM_1, Term.Name.TERM_2],
                'message': 'Please enroll me for the selected terms.',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        request = ReadmissionRequest.objects.get(student=student)
        self.assertEqual(request.status, ReadmissionRequest.Status.PENDING)
        self.assertEqual(request.terms, [Term.Name.TERM_1, Term.Name.TERM_2])
        student.refresh_from_db()
        self.assertEqual(student.school_class_id, previous_class.pk)
        self.assertContains(response, 'awaiting Registrar review')
        self.assertNotContains(
            response, reverse('students:readmission_request')
        )

    def test_registrar_can_approve_readmission_request(self):
        student = User.objects.get(username='student1').student_profile
        school_class = student.school_class
        readmission_request = ReadmissionRequest.objects.create(
            student=student,
            school_class=school_class,
            terms=[Term.Name.TERM_1],
            message='Returning for this term.',
        )
        registrar = self.login('registrar')
        response = self.client.get(
            reverse('students:readmission_request_list')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.student_id)
        response = self.client.post(
            reverse(
                'students:readmission_request_review',
                args=[readmission_request.pk],
            ),
            {'action': 'approve', 'reviewer_note': 'Approved.'},
        )
        self.assertRedirects(
            response, reverse('students:readmission_request_list')
        )
        readmission_request.refresh_from_db()
        student.refresh_from_db()
        self.assertEqual(
            readmission_request.status, ReadmissionRequest.Status.APPROVED
        )
        self.assertEqual(readmission_request.reviewed_by, registrar)
        self.assertTrue(
            student.enrollments.filter(
                school_class=school_class,
                academic_year=school_class.academic_year,
                term=Term.Name.TERM_1,
                is_active=True,
            ).exists()
        )

    def test_student_cannot_submit_duplicate_pending_re_admission_requests(self):
        student = User.objects.get(username='student1').student_profile
        school_class = student.school_class
        self.login('student1')
        request_url = reverse('students:readmission_request')
        request_data = {
            'school_class': school_class.pk,
            'terms': [Term.Name.TERM_1],
            'message': '',
        }
        first_response = self.client.post(request_url, request_data)
        self.assertRedirects(first_response, reverse('accounts:dashboard'))
        second_response = self.client.post(request_url, request_data)
        self.assertRedirects(second_response, reverse('accounts:dashboard'))
        self.assertEqual(
            ReadmissionRequest.objects.filter(
                student=student, status=ReadmissionRequest.Status.PENDING
            ).count(),
            1,
        )

    def test_registrar_can_reject_request_without_changing_enrollment(self):
        student = User.objects.get(username='student1').student_profile
        old_class_id = student.school_class_id
        request = ReadmissionRequest.objects.create(
            student=student,
            school_class=student.school_class,
            terms=[Term.Name.TERM_1],
        )
        self.login('registrar')
        response = self.client.post(
            reverse('students:readmission_request_review', args=[request.pk]),
            {'action': 'reject', 'reviewer_note': 'Please contact the office.'},
        )
        self.assertRedirects(
            response, reverse('students:readmission_request_list')
        )
        request.refresh_from_db()
        student.refresh_from_db()
        self.assertEqual(request.status, ReadmissionRequest.Status.REJECTED)
        self.assertEqual(
            request.reviewer_note, 'Please contact the office.'
        )
        self.assertEqual(student.school_class_id, old_class_id)

    def test_only_registrar_can_review_re_admission_requests(self):
        readmission_request = ReadmissionRequest.objects.create(
            student=User.objects.get(username='student1').student_profile,
            school_class=User.objects.get(
                username='student1'
            ).student_profile.school_class,
            terms=[Term.Name.TERM_1],
        )
        self.login('teacher1')
        response = self.client.get(
            reverse('students:readmission_request_list')
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse(
                'students:readmission_request_review',
                args=[readmission_request.pk],
            ),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 403)

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

    def test_quiz_generation_saves_reviewable_draft(self):
        teacher = self.login('teacher1')
        subject = teacher_subjects(teacher).filter(
            school_classes__students__status=Student.Status.ACTIVE
        ).distinct().first()
        self.assertIsNotNone(subject)
        generated = [{
            'prompt': 'Which number is prime?',
            'options': ['4', '5', '6', '8'],
            'answer': 1,
        }]
        with patch(
            'assignments.views.generate_multiple_choice_questions',
            return_value=generated,
        ):
            response = self.client.post(reverse('assignments:quiz_create'), {
                'subject': subject.pk,
                'title': 'Prime number check',
                'topic': 'Prime numbers',
                'question_count': 1,
                'description': 'Check prime numbers.',
            })
        quiz = Quiz.objects.get(title='Prime number check')
        self.assertRedirects(
            response, reverse('assignments:quiz_detail', args=[quiz.pk])
        )
        self.assertFalse(quiz.is_published)
        question = quiz.questions.get()
        self.assertEqual(question.correct_option, 1)
        response = self.client.post(
            reverse('assignments:quiz_publish', args=[quiz.pk])
        )
        self.assertRedirects(
            response, reverse('assignments:quiz_detail', args=[quiz.pk])
        )
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_published)

    def test_teacher_quiz_list_loads_assigned_subjects(self):
        teacher = self.login('teacher1')
        response = self.client.get(reverse('assignments:quiz_list'))
        self.assertEqual(response.status_code, 200)

    def test_student_quiz_attempt_is_scoped_and_auto_graded_once(self):
        student = User.objects.get(username='student1').student_profile
        subject = Subject.objects.filter(
            school_classes=student.school_class
        ).first()
        quiz = Quiz.objects.create(
            subject=subject,
            title='Science check',
            created_by=User.objects.get(username='teacher1'),
            is_published=True,
        )
        question = QuizQuestion.objects.create(
            quiz=quiz,
            prompt='Select the correct answer.',
            option_a='Wrong',
            option_b='Correct',
            option_c='Wrong',
            option_d='Wrong',
            correct_option=1,
            position=1,
        )
        self.login('student1')
        response = self.client.post(
            reverse('assignments:quiz_attempt', args=[quiz.pk]),
            {f'question_{question.pk}': '1'},
        )
        self.assertRedirects(
            response, reverse('assignments:quiz_detail', args=[quiz.pk])
        )
        attempt = QuizAttempt.objects.get(quiz=quiz, student=student)
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.answers, {str(question.pk): 1})
        self.client.post(
            reverse('assignments:quiz_attempt', args=[quiz.pk]),
            {f'question_{question.pk}': '0'},
        )
        self.assertEqual(QuizAttempt.objects.filter(quiz=quiz, student=student).count(), 1)

    def test_teacher_can_enter_marks_for_assigned_subjects(self):
        teacher = self.login('teacher1')
        subject = teacher_subjects(teacher).filter(
            school_classes__students__status=Student.Status.ACTIVE
        ).distinct().first()
        self.assertIsNotNone(subject)
        exam = Examination.objects.filter(
            academic_year=subject.academic_year,
            school_classes__in=subject.school_classes.all(),
        ).distinct().first()
        self.assertIsNotNone(exam)
        school_class = subject.school_classes.filter(
            pk__in=exam.school_classes.values_list('pk', flat=True)
        ).first()
        student = Student.objects.filter(
            school_class=school_class, status=Student.Status.ACTIVE
        ).first()
        self.assertIsNotNone(student)
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
            examination=exam, subject=subject, student=student
        )
        self.assertEqual(result.marks_obtained, Decimal('77'))
        self.assertEqual(result.entered_by, teacher)

    def test_ai_grading_suggestion_requires_teacher_save(self):
        teacher = self.login('teacher1')
        subject = teacher_subjects(teacher).filter(
            school_classes__students__status=Student.Status.ACTIVE
        ).distinct().first()
        student = Student.objects.filter(
            school_class__in=subject.school_classes.all()
        ).first()
        assignment = Assignment.objects.create(
            subject=subject,
            title='Written assessment',
            description='Explain the topic.',
            due_date=timezone.now() + timedelta(days=1),
            max_score=10,
            created_by=teacher,
        )
        submission = Assignment.objects.get(pk=assignment.pk).submissions.create(
            student=student,
            comment='A short written response.',
        )
        with patch(
            'assignments.views.evaluate_written_submission',
            return_value=(Decimal('8'), 'Clear explanation.'),
        ):
            response = self.client.post(
                reverse('assignments:review', args=[submission.pk]),
                {'ai_suggest': '1'},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['suggested_grade'])
        submission.refresh_from_db()
        self.assertIsNone(submission.score)
        self.assertContains(response, 'Clear explanation.')

    def test_registrar_cannot_view_medical_data(self):
        registrar = User.objects.create_user(
            username='privacy-registrar',
            password='Registrar@12345',
            role=User.Role.REGISTRAR,
        )
        student = Student.objects.first()
        self.client.force_login(registrar)
        response = self.client.get(
            reverse('students:student_detail', args=[student.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Blood Group')
        self.assertNotContains(response, 'Medical Notes')

    def test_school_assistant_handles_missing_key_explicitly(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            response = self.client.post(
                reverse('school_assistant'),
                data='{"question":"When does term begin?"}',
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn('OPENAI_API_KEY', response.json()['error'])

    def test_ai_connection_command_reports_missing_key_without_disclosing_secrets(self):
        from io import StringIO

        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            with self.assertRaisesRegex(
                CommandError, 'OPENAI_API_KEY is not configured'
            ):
                call_command('check_ai', stdout=StringIO())

    def test_ai_client_sends_configured_key_and_model(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            'choices': [{'message': {'content': 'Connection check passed.'}}],
        }).encode('utf-8')
        with (
            patch.dict('os.environ', {
                'OPENAI_API_KEY': 'test-secret',
                'OPENAI_MODEL': 'test-model',
            }),
            patch('school.ai.urlopen', return_value=response) as urlopen,
        ):
            from school.ai import answer_school_question

            answer = answer_school_question(
                'Check connection.', 'Green Hill Secondary School.'
            )
        self.assertEqual(answer, 'Connection check passed.')
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header('Authorization'), 'Bearer test-secret'
        )
        self.assertEqual(json.loads(request.data)['model'], 'test-model')

    def test_ai_client_reports_actionable_provider_http_errors(self):
        from school.ai import AIServiceError, answer_school_question

        failures = {
            401: 'rejected the API key',
            403: 'does not have permission',
            429: 'usage quota was reached',
            400: 'configured model is not available',
        }
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-secret'}):
            for status, expected_message in failures.items():
                with self.subTest(status=status):
                    error = HTTPError(
                        'https://api.openai.com/v1/chat/completions',
                        status,
                        'provider error',
                        None,
                        BytesIO(b''),
                    )
                    with patch('school.ai.urlopen', side_effect=error):
                        with self.assertRaises(AIServiceError) as raised:
                            answer_school_question('Test?', 'Public info.')
                    self.assertIn(expected_message, str(raised.exception))
                    self.assertNotIn('test-secret', str(raised.exception))

    def test_ai_client_uses_default_model_when_configured_model_is_blank(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            'choices': [{'message': {'content': 'Connection check passed.'}}],
        }).encode('utf-8')
        with (
            patch.dict('os.environ', {
                'OPENAI_API_KEY': 'test-secret',
                'OPENAI_MODEL': '  ',
            }),
            patch('school.ai.urlopen', return_value=response) as urlopen,
        ):
            from school.ai import answer_school_question

            answer_school_question('Check connection.', 'Public info.')
        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data)['model'], 'gpt-4o-mini')

    def test_school_assistant_uses_only_public_school_context(self):
        admin_user = User.objects.get(username='admin')
        Announcement.objects.create(
            title='Public office hours',
            message='The office is open on weekdays.',
            audience=Announcement.Audience.ALL,
            is_published=True,
            is_public=True,
            created_by=admin_user,
        )
        Announcement.objects.create(
            title='Private staff note',
            message='This is not public information.',
            audience=Announcement.Audience.TEACHERS,
            is_published=True,
            is_public=False,
            created_by=admin_user,
        )
        with patch(
            'school.views.answer_school_question',
            return_value='Contact the school office.',
        ) as assistant:
            response = self.client.post(
                reverse('school_assistant'),
                data='{"question":"When is the office open?"}',
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['answer'], 'Contact the school office.')
        context = assistant.call_args.args[1]
        self.assertIn('Public office hours', context)
        self.assertNotIn('Private staff note', context)

    def test_student_archive_and_restore_preserve_history_and_access(self):
        registrar = User.objects.create_user(
            username='registrar-test',
            password='Registrar@12345',
            role=User.Role.REGISTRAR,
        )
        student = Student.objects.select_related('user').first()
        original_username = student.user.username
        self.client.force_login(registrar)

        response = self.client.post(
            reverse('students:student_delete', args=[student.pk])
        )
        self.assertRedirects(response, reverse('students:student_list'))
        student.refresh_from_db()
        student.user.refresh_from_db()
        self.assertTrue(student.is_archived)
        self.assertFalse(student.user.is_active)
        self.assertTrue(student.enrollments.exists())

        response = self.client.post(
            reverse('students:student_restore', args=[student.pk])
        )
        self.assertRedirects(response, reverse('students:archived_students'))
        student.refresh_from_db()
        student.user.refresh_from_db()
        self.assertFalse(student.is_archived)
        self.assertTrue(student.user.is_active)
        self.assertEqual(student.user.username, original_username)

    def test_student_readmission_keeps_id_and_prior_enrollments(self):
        registrar = User.objects.create_user(
            username='readmit-registrar',
            password='Registrar@12345',
            role=User.Role.REGISTRAR,
        )
        student = Student.objects.select_related('school_class').first()
        old_class_id = student.school_class_id
        old_student_id = student.student_id
        new_class = SchoolClass.objects.exclude(pk=old_class_id).first()
        self.client.force_login(registrar)
        response = self.client.post(
            reverse('students:student_readmit', args=[student.pk]),
            {
                'school_class': new_class.pk,
                'terms': [Term.Name.TERM_1],
                'admission_date': timezone.localdate().isoformat(),
            },
        )
        self.assertRedirects(
            response, reverse('students:student_detail', args=[student.pk])
        )
        student.refresh_from_db()
        self.assertEqual(student.student_id, old_student_id)
        self.assertEqual(student.school_class_id, new_class.pk)
        self.assertFalse(
            student.enrollments.filter(
                school_class_id=old_class_id, is_active=True
            ).exists()
        )
        self.assertTrue(
            student.enrollments.filter(
                school_class=new_class,
                academic_year=new_class.academic_year,
                term=Term.Name.TERM_1,
                is_active=True,
            ).exists()
        )

    def test_exam_eligibility_requires_every_current_fee_paid(self):
        student = Student.objects.select_related('school_class').first()
        year = student.school_class.academic_year
        Payment.objects.filter(student=student).delete()
        for applicable_fee in active_fees_for_student(student):
            Payment.objects.create(
                student=student,
                fee=applicable_fee,
                amount=applicable_fee.amount,
                method=Payment.Method.CASH,
            )
        self.assertTrue(exam_eligibility_for_student(student)['eligible'])
        fee = Fee.objects.create(
            name='Eligibility test fee',
            school_class=student.school_class,
            academic_year=year,
            amount=Decimal('125.00'),
            is_active=True,
        )
        second_fee = Fee.objects.create(
            name='Eligibility second test fee',
            school_class=student.school_class,
            academic_year=year,
            amount=Decimal('50.00'),
            is_active=True,
        )
        eligibility = exam_eligibility_for_student(student)
        self.assertFalse(
            eligibility['eligible'],
            f'{eligibility}; new fee {fee.pk}; '
            f'current fees {list(active_fees_for_student(student).values_list("pk", "amount"))}',
        )
        self.assertGreaterEqual(fee_totals_for_student(student)[2], Decimal('125.00'))
        Payment.objects.create(
            student=student,
            fee=fee,
            amount=Decimal('125.00'),
            method=Payment.Method.CASH,
        )
        self.assertFalse(exam_eligibility_for_student(student)['eligible'])
        Payment.objects.create(
            student=student,
            fee=second_fee,
            amount=Decimal('50.00'),
            method=Payment.Method.CASH,
        )
        self.assertTrue(exam_eligibility_for_student(student)['eligible'])

    def test_student_dashboard_shows_professional_eligible_status_panel(self):
        student = User.objects.get(username='student1').student_profile
        Payment.objects.filter(student=student).delete()
        fees = list(active_fees_for_student(student))
        self.assertTrue(fees)
        for fee in fees:
            Payment.objects.create(
                student=student,
                fee=fee,
                amount=fee.amount,
                method=Payment.Method.CASH,
            )

        self.login('student1')
        response = self.client.get(reverse('accounts:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'eligibility-panel--eligible')
        self.assertContains(response, 'Eligible to sit')
        self.assertContains(response, '100%')
        self.assertContains(response, 'All active fees')
        self.assertContains(
            response, reverse('finance:fee_statement', args=[student.pk])
        )
        self.assertEqual(response.context['exam_eligibility_progress'], 100)

    def test_student_dashboard_explains_outstanding_eligibility_and_progress(self):
        student = User.objects.get(username='student1').student_profile
        Payment.objects.filter(student=student).delete()
        first_fee = active_fees_for_student(student).first()
        self.assertIsNotNone(first_fee)
        Payment.objects.create(
            student=student,
            fee=first_fee,
            amount=first_fee.amount / Decimal('2'),
            method=Payment.Method.CASH,
        )
        self.login('student1')

        response = self.client.get(reverse('accounts:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'eligibility-panel--outstanding')
        self.assertContains(response, 'Payment required')
        self.assertContains(response, 'outstanding fee balance')
        self.assertContains(response, 'Outstanding')
        self.assertContains(
            response, reverse('finance:fee_statement', args=[student.pk])
        )
        self.assertLess(response.context['exam_eligibility_progress'], 100)
        self.assertGreater(response.context['exam_eligibility_progress'], 0)

    def test_student_dashboard_shows_unassessed_when_no_active_fees_exist(self):
        student = User.objects.get(username='student1').student_profile
        Fee.objects.filter(
            academic_year=student.school_class.academic_year
        ).update(is_active=False)
        self.login('student1')

        response = self.client.get(reverse('accounts:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'eligibility-panel--unavailable')
        self.assertContains(response, 'Not assessed')
        self.assertContains(response, 'eligibility cannot be assessed')
        self.assertNotContains(response, 'Payment progress')
        self.assertContains(
            response, reverse('finance:fee_statement', args=[student.pk])
        )
