from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.domain.employees"
    verbose_name = "Управление сотрудниками"
