import json
import logging
import os
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.db.models import Count, Q
from django.utils.encoding import force_text
from rest_framework.renderers import JSONRenderer

from .models import Task
from .serializers import TaskSerializer

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Sends task lifecycle events to an external webhook endpoint."""

    def __init__(self):
        self.webhook_url = getattr(settings, "TASK_WEBHOOK_URL", None)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "TaskTracker/1.0",
        })
        api_key = os.environ.get("WEBHOOK_API_KEY", "")
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def notify(self, event, task):
        if not self.webhook_url:
            return

        serializer = TaskSerializer(task)
        renderer = JSONRenderer()
        task_json = json.loads(renderer.render(serializer.data))

        # force_text was renamed to force_str in Django 4.0 (removed fully
        # in 5.0). Forcing a string here guarantees the event name is a
        # native str even if callers pass bytes/lazy translations.
        payload = {
            "event": force_text(event),
            "task": task_json,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        try:
            resp = self.session.post(self.webhook_url, json=payload, timeout=5)
            resp.raise_for_status()
            logger.info("webhook %s sent for task %d", event, task.id)
        except requests.ConnectionError:
            logger.warning("webhook unreachable for %s on task %d", event, task.id)
        except requests.HTTPError as exc:
            logger.warning("webhook %s failed for task %d: %s", event, task.id, exc.response.status_code)
        except requests.Timeout:
            logger.warning("webhook %s timed out for task %d", event, task.id)

    def on_created(self, task):
        self.notify("task.created", task)

    def on_updated(self, task):
        self.notify("task.updated", task)

    def on_deleted(self, task):
        self.notify("task.deleted", task)

    def on_status_changed(self, task, old_status):
        serializer = TaskSerializer(task)
        renderer = JSONRenderer()
        task_json = json.loads(renderer.render(serializer.data))

        payload = {
            "event": "task.status_changed",
            "task": task_json,
            "old_status": old_status,
            "new_status": task.status,
        }

        if not self.webhook_url:
            return

        try:
            self.session.post(self.webhook_url, json=payload, timeout=5)
        except requests.RequestException:
            logger.debug("webhook status_changed failed for task %d", task.id)


class TaskAnalytics:
    """Computes task analytics and optionally syncs summaries to an external dashboard."""

    def get_summary(self):
        total = Task.objects.count()
        if total == 0:
            return {"total": 0, "by_status": {}, "by_priority": {}, "completion_rate": 0.0, "generated_at": datetime.now(tz=timezone.utc).isoformat()}

        status_counts = dict(
            Task.objects.values_list("status").annotate(cnt=Count("id")).values_list("status", "cnt")
        )
        priority_counts = dict(
            Task.objects.values_list("priority").annotate(cnt=Count("id")).values_list("priority", "cnt")
        )

        done = status_counts.get("done", 0)
        completion_rate = (done / total) * 100

        overdue_high = Task.objects.filter(
            Q(priority="high") & ~Q(status="done")
        ).count()

        return {
            "total": total,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "completion_rate": round(completion_rate, 1),
            "overdue_high_priority": overdue_high,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def sync_to_dashboard(self):
        dashboard_url = getattr(settings, "DASHBOARD_SYNC_URL", None)
        if not dashboard_url:
            return None

        summary = self.get_summary()

        try:
            resp = requests.put(dashboard_url, json=summary, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("dashboard sync failed: %s", exc)
            return None


class ExternalTaskImporter:
    """Imports tasks from an external REST API."""

    def __init__(self, api_url):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"

    def fetch_and_import(self, max_items=50):
        try:
            resp = self.session.get(self.api_url, timeout=10, params={"limit": max_items})
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("failed to fetch tasks from %s: %s", self.api_url, exc)
            return 0

        items = resp.json()
        if isinstance(items, dict):
            items = items.get("results", items.get("data", items.get("tasks", [])))

        created = 0
        for item in items[:max_items]:
            serializer = TaskSerializer(data={
                "title": item.get("title", item.get("name", "Imported task")),
                "description": item.get("description", item.get("body", "")),
                "priority": self._map_priority(item.get("priority", "medium")),
            })
            if serializer.is_valid():
                serializer.save()
                created += 1

        logger.info("imported %d tasks from %s", created, self.api_url)
        return created

    @staticmethod
    def _map_priority(value):
        mapping = {"urgent": "high", "critical": "high", "normal": "medium", "minor": "low"}
        return mapping.get(str(value).lower(), "medium")
