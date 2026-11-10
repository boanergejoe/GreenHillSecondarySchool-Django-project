from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Super Administrator'
        TEACHER = 'teacher', 'Teacher / Lecturer'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent / Guardian'
        ACCOUNTANT = 'accountant', 'Accountant'
        REGISTRAR = 'registrar', 'Registrar'
        DOS = 'dos', 'Director of Studies (DOS)'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(upload_to='users/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['first_name', 'last_name', 'username']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_super_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT

    @property
    def is_accountant(self):
        return self.role == self.Role.ACCOUNTANT

    @property
    def is_dos(self):
        return self.role == self.Role.DOS

    @property
    def initials(self):
        first = self.first_name[:1] if self.first_name else self.username[:1]
        last = self.last_name[:1] if self.last_name else ''
        return f'{first}{last}'.upper()
