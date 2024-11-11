from django import forms

from src.domain.employees.models import Employee


class EmployeeCreationForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "username",
            "fio",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
        )

    def save(self, commit=True):
        user = super(EmployeeCreationForm, self).save(commit=False)
        if commit:
            user.save()
        return user
