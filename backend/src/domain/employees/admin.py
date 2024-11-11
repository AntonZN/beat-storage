from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import EmployeeCreationForm
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(UserAdmin):
    add_form = EmployeeCreationForm

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "fio",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                ),
            },
        ),
    )
    list_display = (
        "username",
        "fio",
    )

    list_filter = ("is_superuser",)
    search_fields = ("username", "fio")
    ordering = ("username",)

    def get_exclude(self, request, obj=None):
        if not self.exclude:
            self.exclude = tuple()

        if request.user.is_superuser:
            return self.exclude
        else:
            return self.exclude + ("is_superuser", "groups")

    def get_fieldsets(self, request, obj=None):
        main = (
            "Основное",
            {
                "fields": (
                    "username",
                    "fio",
                )
            },
        )

        all_permissions = (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                )
            },
        )

        if request.user.is_superuser:
            fieldsets = (main, all_permissions)
        else:
            fieldsets = (main,)

        return fieldsets

    def get_readonly_fields(self, request, obj: Employee = None):
        if request.user.is_superuser:
            return self.readonly_fields

        else:
            return self.readonly_fields + ("is_superuser",)

