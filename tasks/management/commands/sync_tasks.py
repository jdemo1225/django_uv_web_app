import json
from datetime import datetime, timezone

import requests
from django.core.management.base import BaseCommand, CommandError
from rest_framework.renderers import JSONRenderer

from tasks.models import Task
from tasks.serializers import TaskSerializer
from tasks.services import ExternalTaskImporter, TaskAnalytics


class Command(BaseCommand):
    help = "Sync tasks with an external service: import, export, or push analytics"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action")

        import_parser = subparsers.add_parser("import", help="Import tasks from an external API")
        import_parser.add_argument("--url", required=True, help="API URL to fetch tasks from")
        import_parser.add_argument("--max", type=int, default=50, help="Maximum tasks to import")

        export_parser = subparsers.add_parser("export", help="Export tasks to an external API")
        export_parser.add_argument("--url", required=True, help="API URL to push tasks to")
        export_parser.add_argument("--status", help="Filter by status (todo, in_progress, done)")

        subparsers.add_parser("analytics", help="Print task analytics summary")

    def handle(self, *args, **options):
        action = options.get("action")
        if action == "import":
            self._handle_import(options)
        elif action == "export":
            self._handle_export(options)
        elif action == "analytics":
            self._handle_analytics()
        else:
            self.stdout.write(self.style.WARNING("Usage: sync_tasks {import|export|analytics}"))

    def _handle_import(self, options):
        url = options["url"]
        max_items = options["max"]

        importer = ExternalTaskImporter(url)
        count = importer.fetch_and_import(max_items=max_items)
        self.stdout.write(self.style.SUCCESS(f"Imported {count} tasks from {url}"))

    def _handle_export(self, options):
        url = options["url"]
        status_filter = options.get("status")

        tasks = Task.objects.all()
        if status_filter:
            tasks = tasks.filter(status=status_filter)

        serializer = TaskSerializer(tasks, many=True)
        renderer = JSONRenderer()
        payload = json.loads(renderer.render(serializer.data))

        try:
            resp = requests.post(url, json={"tasks": payload, "exported_at": datetime.now(tz=timezone.utc).isoformat()}, timeout=15)
            resp.raise_for_status()
            self.stdout.write(self.style.SUCCESS(
                f"Exported {len(payload)} tasks to {url} (HTTP {resp.status_code})"
            ))
        except requests.ConnectionError:
            raise CommandError(f"Could not connect to {url}")
        except requests.HTTPError as exc:
            raise CommandError(f"Export failed: HTTP {exc.response.status_code}")
        except requests.Timeout:
            raise CommandError(f"Export to {url} timed out")

    def _handle_analytics(self):
        analytics = TaskAnalytics()
        summary = analytics.get_summary()

        self.stdout.write(f"Total tasks: {summary['total']}")
        self.stdout.write(f"Completion rate: {summary['completion_rate']}%")
        self.stdout.write(f"High-priority open: {summary['overdue_high_priority']}")

        self.stdout.write("\nBy status:")
        for s, count in summary["by_status"].items():
            self.stdout.write(f"  {s}: {count}")

        self.stdout.write("\nBy priority:")
        for p, count in summary["by_priority"].items():
            self.stdout.write(f"  {p}: {count}")
