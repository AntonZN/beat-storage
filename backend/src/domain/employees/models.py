from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class EmployeeManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Имя пользователя обязательно")

        extra_fields.setdefault("is_active", True)

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(username, password, **extra_fields)


class Employee(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    fio = models.CharField("ФИО", max_length=255)
    is_active = models.BooleanField(
        "Активен",
        help_text=(
            "По умолчанию при создании сотрудник активен, "
            "чтобы сотрудник не имел доступа к системе уберите этот флаг"
        ),
        default=True,
    )
    is_staff = models.BooleanField("Разрешить доступ в админ панель", default=False)

    objects = EmployeeManager()

    USERNAME_FIELD = "username"

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return self.username
