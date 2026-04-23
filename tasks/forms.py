from django import forms

from .models import Task


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "What needs to be done?"}),
            "description": forms.Textarea(attrs={"placeholder": "Optional details...", "rows": 4}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
