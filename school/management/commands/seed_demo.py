from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from academics.models import (
    AcademicYear, Department, Enrollment, SchoolClass, Subject, Term,
)
from accounts.models import User
from assignments.models import Assignment, Submission
from attendance.models import Attendance
from communications.models import Announcement, Notification
from examinations.models import Examination, Result
from finance.models import Fee, Payment
from students.models import Parent, Student
from teachers.models import Teacher


class Command(BaseCommand):
    help = 'Create idempotent demo data for Green Hill Secondary School.'

    def _user(self, username, password, role, first_name, last_name, email=''):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'role': role,
                'is_active': True,
                'is_staff': role == User.Role.ADMIN,
                'is_superuser': role == User.Role.ADMIN,
            },
        )
        user.set_password(password)
        user.save(update_fields=['password'])
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        admin = self._user(
            'admin', 'Admin@12345', User.Role.ADMIN,
            'System', 'Administrator', 'admin@greenhillss.edu.ss',
        )
        accountant = self._user(
            'accountant', 'Account@12345', User.Role.ACCOUNTANT,
            'Mary', 'Achol', 'accounts@greenhillss.edu.ss',
        )

        year, _ = AcademicYear.objects.update_or_create(
            name='2026',
            defaults={
                'start_date': today.replace(month=2, day=2),
                'end_date': today.replace(month=11, day=27),
                'is_current': True,
            },
        )
        term_windows = [
            ('Term 1', (2, 2), (5, 8)),
            ('Term 2', (5, 25), (8, 21)),
            ('Term 3', (9, 7), (11, 27)),
        ]
        terms = []
        for name, start, end in term_windows:
            term, _ = Term.objects.update_or_create(
                name=name,
                academic_year=year,
                defaults={
                    'start_date': today.replace(month=start[0], day=start[1]),
                    'end_date': today.replace(month=end[0], day=end[1]),
                },
            )
            terms.append(term)
        current_term = next(
            (term for term in terms if term.start_date <= today <= term.end_date),
            terms[0],
        )
        Term.objects.filter(academic_year=year).exclude(pk=current_term.pk).update(
            is_current=False
        )
        Term.objects.filter(pk=current_term.pk).update(is_current=True)
        current_term.is_current = True

        Fee.objects.update_or_create(
            name='Registration Fee',
            school_class=None,
            academic_year=year,
            defaults={
                'term': current_term.name,
                'amount': Decimal('25000.00'),
                'due_date': today.replace(month=2, day=20),
                'is_active': True,
                'description': 'Annual registration fee for every student, regardless of class or department.',
            },
        )

        sciences = Department.objects.filter(
            Q(name__iexact='Science') | Q(name__iexact='Sciences') | Q(code__iexact='SCI')
        ).first()
        if sciences:
            sciences.name = 'Science'
            sciences.code = 'SCI'
            sciences.description = 'Science and mathematics subjects.'
            sciences.save(update_fields=['name', 'code', 'description'])
        else:
            sciences = Department.objects.create(
                code='SCI', name='Science',
                description='Science and mathematics subjects.',
            )

        arts = Department.objects.filter(
            Q(name__iexact='Arts') | Q(code__iexact='ART')
        ).first()
        if arts:
            arts.name = 'Arts'
            arts.code = 'ART'
            arts.description = 'Languages, humanities and social sciences.'
            arts.save(update_fields=['name', 'code', 'description'])
        else:
            arts = Department.objects.create(
                code='ART', name='Arts',
                description='Languages, humanities and social sciences.',
            )

        teacher_users = [
            self._user(
                'teacher1', 'Teacher@12345', User.Role.TEACHER,
                'Sarah', 'Deng', 'sarah.deng@greenhillss.edu.ss',
            ),
            self._user(
                'teacher2', 'Teacher@12345', User.Role.TEACHER,
                'Emmanuel', 'Lado', 'emmanuel.lado@greenhillss.edu.ss',
            ),
            self._user(
                'teacher3', 'Teacher@12345', User.Role.TEACHER,
                'Grace', 'Kiden', 'grace.kiden@greenhillss.edu.ss',
            ),
            self._user(
                'teacher4', 'Teacher@12345', User.Role.TEACHER,
                'Peter', 'Wani', 'peter.wani@greenhillss.edu.ss',
            ),
        ]
        teacher_data = [
            (sciences, 'MSc Mathematics', 'Mathematics and Physics', 'Block A, Room 4'),
            (arts, 'BA English', 'English and Geography', 'Block B, Room 2'),
            (sciences, 'BSc Biology', 'Biology and Chemistry', 'Block A, Room 7'),
            (arts, 'BSc ICT', 'ICT and Digital Studies', 'Block C, Room 1'),
        ]
        teachers = []
        for index, (user, (department, qualification, specialization, office)) in enumerate(
            zip(teacher_users, teacher_data), start=1
        ):
            staff_id = f'GSS-T-2026-{index:03d}'
            teacher = Teacher.objects.filter(
                Q(user=user) | Q(staff_id=staff_id)
            ).first()
            if not teacher:
                teacher = Teacher(user=user)
            teacher.user = user
            teacher.staff_id = staff_id
            teacher.department = department
            teacher.qualification = qualification
            teacher.specialization = specialization
            teacher.employment_type = Teacher.EmploymentType.FULL_TIME
            teacher.status = Teacher.Status.ACTIVE
            teacher.office = office
            teacher.save()
            teachers.append(teacher)

        classes = []
        class_data = [
            (SchoolClass.Level.SENIOR_1, 'Senior 1 A', '', 'Room 1', None),
            (SchoolClass.Level.SENIOR_2, 'Senior 2 A', '', 'Room 2', None),
            (SchoolClass.Level.SENIOR_3, 'Senior 3 Arts', SchoolClass.Stream.ARTS, 'Room 3', arts),
            (SchoolClass.Level.SENIOR_3, 'Senior 3 Science', SchoolClass.Stream.SCIENCE, 'Room 3B', sciences),
            (SchoolClass.Level.SENIOR_4, 'Senior 4 Arts', SchoolClass.Stream.ARTS, 'Room 4', arts),
            (SchoolClass.Level.SENIOR_4, 'Senior 4 Science', SchoolClass.Stream.SCIENCE, 'Room 4B', sciences),
        ]
        for index, (level, name, stream, room, department) in enumerate(class_data):
            school_class, _ = SchoolClass.objects.update_or_create(
                name=name,
                academic_year=year,
                defaults={
                    'level': level,
                    'stream': stream,
                    'department': department,
                    'class_teacher': teacher_users[index % len(teacher_users)],
                    'capacity': 45,
                    'room': room,
                },
            )
            classes.append(school_class)

        for index, teacher in enumerate(teachers):
            teacher.assigned_classes.set(classes[index::len(teachers)])

        for legacy_class in SchoolClass.objects.filter(
            academic_year=year, name__in=['Senior 3 A', 'Senior 4 A']
        ).exclude(pk__in=[school_class.pk for school_class in classes]):
            if not legacy_class.students.exists():
                legacy_class.delete()

        subject_data = {
            'MATH': {
                'name': 'Mathematics',
                'teacher': teachers[0],
                'departments': [arts, sciences],
            },
            'ENG': {
                'name': 'English Language',
                'teacher': teachers[1],
                'departments': [arts, sciences],
            },
            'ICT': {
                'name': 'ICT',
                'teacher': teachers[3],
                'departments': [arts, sciences],
            },
            'BIO': {
                'name': 'Biology',
                'teacher': teachers[2],
                'departments': [sciences],
            },
            'CHEM': {
                'name': 'Chemistry',
                'teacher': teachers[2],
                'departments': [sciences],
            },
            'PHY': {
                'name': 'Physics',
                'teacher': teachers[0],
                'departments': [sciences],
            },
            'GEO': {
                'name': 'Geography',
                'teacher': teachers[1],
                'departments': [arts],
            },
        }
        shared_codes = ['MATH', 'ENG', 'ICT']
        subjects_by_class = {}
        for school_class in classes:
            if school_class.level in (
                SchoolClass.Level.SENIOR_3, SchoolClass.Level.SENIOR_4,
            ):
                subject_codes = shared_codes + (
                    ['GEO'] if school_class.stream == SchoolClass.Stream.ARTS
                    else ['BIO', 'CHEM', 'PHY']
                )
            else:
                subject_codes = shared_codes

            subjects = []
            for code in subject_codes:
                data = subject_data[code]
                subject = Subject.objects.filter(
                    code=code,
                    academic_year=year,
                    school_classes=school_class,
                ).first()
                if subject:
                    subject.name = data['name']
                    subject.teacher = data['teacher'].user
                    subject.term = current_term.name
                    subject.is_active = True
                    subject.save()
                else:
                    subject = Subject.objects.create(
                        code=code,
                        name=data['name'],
                        teacher=data['teacher'].user,
                        academic_year=year,
                        term=current_term.name,
                        is_active=True,
                    )
                subject.school_classes.add(school_class)
                subject.departments.set(data['departments'])
                subjects.append(subject)
            for stale_subject in school_class.subjects.exclude(code__in=subject_codes):
                if stale_subject.results.exists():
                    stale_subject.is_active = False
                    stale_subject.save(update_fields=['is_active'])
                else:
                    stale_subject.delete()
            subjects_by_class[school_class.pk] = subjects

        parent_data = [
            ('parent1', 'John', 'Malo', 'father', 'Trader'),
            ('parent2', 'Rebecca', 'Nyibol', 'mother', 'Teacher'),
            ('parent3', 'Daniel', 'Lual', 'guardian', 'Civil Servant'),
        ]
        parents = []
        for index, (username, first, last, relationship, occupation) in enumerate(
            parent_data, start=1
        ):
            parent_user = self._user(
                username, 'Parent@12345', User.Role.PARENT, first, last,
                f'{username}@example.com',
            )
            parent, _ = Parent.objects.update_or_create(
                user=parent_user,
                defaults={
                    'relationship': relationship,
                    'occupation': occupation,
                    'address': 'Juba, South Sudan',
                    'alternate_phone': f'+211 900 100 {index:03d}',
                },
            )
            parents.append(parent)

        student_data = [
            ('student1', 'Ajak', 'Malo', 'female', classes[0], parents[0], arts),
            ('student2', 'Bol', 'Malo', 'male', classes[0], parents[0], sciences),
            ('student3', 'Chol', 'Nyibol', 'male', classes[0], parents[1], arts),
            ('student4', 'Adut', 'Nyibol', 'female', classes[1], parents[1], sciences),
            ('student5', 'Lual', 'Lual', 'male', classes[1], parents[2], arts),
            ('student6', 'Akuol', 'Lual', 'female', classes[1], parents[2], sciences),
        ]
        students = []
        for index, (
            username, first, last, gender, school_class, parent, department,
        ) in enumerate(
            student_data, start=1
        ):
            student_user = self._user(
                username, 'Student@12345', User.Role.STUDENT, first, last,
                f'{username}@example.com',
            )
            student, _ = Student.objects.update_or_create(
                user=student_user,
                defaults={
                    'student_id': f'GSS-2026-{index:03d}',
                    'school_class': school_class,
                    'department': department,
                    'parent': parent,
                    'admission_date': today.replace(month=2, day=5),
                    'date_of_birth': today.replace(year=today.year - (14 + index), month=5, day=10),
                    'gender': gender,
                    'status': Student.Status.ACTIVE,
                    'address': 'Juba, South Sudan',
                    'guardian_name': parent.user.display_name,
                    'guardian_phone': parent.user.phone or '+211 900 000 000',
                    'blood_group': 'O+',
                },
            )
            Enrollment.objects.update_or_create(
                student=student,
                school_class=school_class,
                academic_year=year,
                term=current_term.name,
                defaults={
                    'enrolled_on': student.admission_date,
                    'is_active': student.status == Student.Status.ACTIVE,
                },
            )
            students.append(student)

        tuition_by_class = {
            'Senior 1 A': Decimal('75000.00'),
            'Senior 2 A': Decimal('75000.00'),
            'Senior 3 Arts': Decimal('85000.00'),
            'Senior 3 Science': Decimal('95000.00'),
            'Senior 4 Arts': Decimal('90000.00'),
            'Senior 4 Science': Decimal('100000.00'),
        }
        for school_class in classes:
            tuition, _ = Fee.objects.update_or_create(
                name='Tuition Fee',
                school_class=school_class,
                academic_year=year,
                defaults={
                    'term': current_term.name,
                    'amount': tuition_by_class[school_class.name],
                    'due_date': today.replace(month=3, day=15),
                    'is_active': True,
                    'description': 'Term tuition and academic services.',
                },
            )
            Fee.objects.update_or_create(
                name='Examination Fee',
                school_class=school_class,
                academic_year=year,
                defaults={
                    'term': current_term.name,
                    'amount': Decimal('15000.00'),
                    'due_date': today.replace(month=4, day=10),
                    'is_active': True,
                    'description': 'Examination preparation and materials.',
                },
            )
            for student in Student.objects.filter(school_class=school_class):
                Payment.objects.update_or_create(
                    student=student,
                    fee=tuition,
                    defaults={
                        'amount': Decimal('50000.00'),
                        'payment_date': today - timedelta(days=10),
                        'method': Payment.Method.MOBILE,
                        'reference': f'MOB-{student.student_id[-3:]}',
                        'recorded_by': accountant,
                        'remarks': 'Part payment of tuition.',
                    },
                )

        exam, _ = Examination.objects.update_or_create(
            name='Term 1 Midterm Examination',
            academic_year=year,
            defaults={
                'exam_type': Examination.ExamType.MIDTERM,
                'term': current_term.name,
                'start_date': today - timedelta(days=14),
                'end_date': today - timedelta(days=10),
                'total_marks': 100,
                'is_published': True,
            },
        )
        exam.school_classes.set([classes[0]])
        result_marks = [88, 76, 69, 81, 74, 63, 90]
        for student_index, student in enumerate(
            Student.objects.filter(school_class=classes[0]).order_by('student_id')
        ):
            for subject_index, subject in enumerate(subjects_by_class[classes[0].pk]):
                mark = result_marks[(student_index + subject_index) % len(result_marks)]
                Result.objects.update_or_create(
                    student=student,
                    examination=exam,
                    subject=subject,
                    defaults={
                        'marks_obtained': Decimal(mark),
                        'total_marks': Decimal('100'),
                        'remarks': 'Keep up the good work.' if mark >= 70 else 'Needs improvement.',
                        'entered_by': subject.teacher,
                    },
                )

        statuses = [
            Attendance.Status.PRESENT, Attendance.Status.PRESENT,
            Attendance.Status.LATE, Attendance.Status.PRESENT,
            Attendance.Status.ABSENT, Attendance.Status.EXCUSED,
        ]
        for school_class in classes[:2]:
            class_subjects = subjects_by_class[school_class.pk]
            for student_index, student in enumerate(
                Student.objects.filter(school_class=school_class).order_by('student_id')
            ):
                for day_offset in range(3):
                    record_date = today - timedelta(days=day_offset)
                    status = statuses[(student_index + day_offset) % len(statuses)]
                    Attendance.objects.update_or_create(
                        student=student,
                        school_class=school_class,
                        subject=None,
                        date=record_date,
                        defaults={
                            'status': status,
                            'recorded_by': school_class.class_teacher,
                            'remarks': 'Daily attendance.',
                        },
                    )
                    Attendance.objects.update_or_create(
                        student=student,
                        school_class=school_class,
                        subject=class_subjects[0],
                        date=record_date,
                        defaults={
                            'status': status,
                            'recorded_by': class_subjects[0].teacher,
                        },
                    )

        for school_class in classes[:2]:
            class_subjects = subjects_by_class[school_class.pk]
            for subject in class_subjects[:2]:
                title = f'{subject.name} Practice Set'
                assignment = Assignment.objects.filter(
                    subject=subject, title=title
                ).order_by('pk').first()
                defaults = {
                    'description': f'Complete the practice questions for {subject.name}.',
                    'due_date': now + timedelta(days=7),
                    'max_score': 50,
                    'created_by': subject.teacher,
                    'is_published': True,
                }
                if assignment:
                    for field, value in defaults.items():
                        setattr(assignment, field, value)
                    assignment.save(update_fields=list(defaults))
                else:
                    assignment = Assignment.objects.create(
                        subject=subject, title=title, **defaults
                    )
                student = Student.objects.filter(school_class=school_class).first()
                if student:
                    Submission.objects.update_or_create(
                        assignment=assignment,
                        student=student,
                        defaults={
                            'comment': 'Completed the practice set.',
                            'status': Submission.Status.SUBMITTED,
                        },
                    )

        welcome, _ = Announcement.objects.update_or_create(
            title='Welcome to the 2026 Academic Year',
            defaults={
                'message': (
                    'Welcome back to Green Hill Secondary School. Classes begin promptly at 8:00 AM. '
                    'Please ensure all fees are settled and bring your learning materials.'
                ),
                'audience': Announcement.Audience.ALL,
                'event_date': year.start_date,
                'is_published': True,
                'created_by': admin,
            },
        )
        Announcement.objects.update_or_create(
            title='Parents and Teachers Meeting',
            defaults={
                'message': (
                    'A parents and teachers meeting will be held in the school hall to discuss '
                    'academic progress and the term ahead.'
                ),
                'audience': Announcement.Audience.PARENTS,
                'event_date': today + timedelta(days=14),
                'is_published': True,
                'created_by': admin,
            },
        )
        for user in User.objects.filter(is_active=True):
            Notification.objects.get_or_create(
                user=user,
                title=welcome.title,
                defaults={
                    'message': welcome.message[:240],
                    'link': f'/communications/announcements/{welcome.pk}/',
                },
            )

        self.stdout.write(self.style.SUCCESS('Demo data created successfully.'))
        self.stdout.write('Login accounts:')
        self.stdout.write('  admin / Admin@12345')
        self.stdout.write('  accountant / Account@12345')
        self.stdout.write('  teacher1 / Teacher@12345')
        self.stdout.write('  student1 / Student@12345')
        self.stdout.write('  parent1 / Parent@12345')
