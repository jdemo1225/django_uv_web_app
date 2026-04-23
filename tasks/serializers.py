from datetime import datetime, timezone

from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ["id", "title", "description", "priority", "status", "is_archived",
                  "due_date", "is_overdue", "created_at", "updated_at"]
        read_only_fields = ["id", "is_overdue", "created_at", "updated_at"]

    def get_is_overdue(self, obj):
        if obj.due_date is None:
            return False
        return obj.due_date < datetime.now(tz=timezone.utc) and obj.status != "done"
