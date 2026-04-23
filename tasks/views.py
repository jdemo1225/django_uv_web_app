import os
from datetime import datetime, timezone

import requests
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .forms import TaskForm
from .models import Task
from .serializers import TaskSerializer
from .services import TaskAnalytics, ExternalTaskImporter


# --- HTML Views ---

def index(request):
    filter_status = request.GET.get("status", "all")
    if filter_status == "all":
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(status=filter_status)

    counts = {
        "all": Task.objects.count(),
        "todo": Task.objects.filter(status="todo").count(),
        "in_progress": Task.objects.filter(status="in_progress").count(),
        "done": Task.objects.filter(status="done").count(),
    }
    return render(request, "tasks/index.html", {
        "tasks": tasks,
        "filter_status": filter_status,
        "counts": counts,
    })


def add_task(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Task created!")
            return redirect("index")
    else:
        form = TaskForm()
    return render(request, "tasks/form.html", {"form": form, "action": "Add"})


def edit_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated!")
            return redirect("index")
    else:
        form = TaskForm(instance=task)
    return render(request, "tasks/form.html", {"form": form, "action": "Edit"})


def toggle_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    old_status = task.status
    transitions = {"todo": "in_progress", "in_progress": "done", "done": "todo"}
    task.status = transitions.get(task.status, "todo")
    task.save()
    # Signal fires via post_save, but status_changed needs explicit call
    from .services import WebhookNotifier
    WebhookNotifier().on_status_changed(task, old_status)
    return redirect(request.META.get("HTTP_REFERER", "index"))


def delete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if request.method == "POST":
        task.delete()
        messages.info(request, "Task deleted.")
    return redirect("index")


def stats(request):
    total = Task.objects.count()

    status_qs = Task.objects.values("status").annotate(cnt=Count("id"))
    status_stats = {row["status"]: row["cnt"] for row in status_qs}

    priority_qs = Task.objects.values("priority").annotate(cnt=Count("id"))
    priority_stats = {row["priority"]: row["cnt"] for row in priority_qs}

    latest = Task.objects.first()

    now = datetime.now(tz=timezone.utc)
    overdue = Task.objects.filter(due_date__lt=now).exclude(status="done")

    return render(request, "tasks/stats.html", {
        "total": total,
        "status_stats": status_stats,
        "priority_stats": priority_stats,
        "latest": latest,
        "overdue_count": overdue.count(),
    })


def inspiration(request):
    quote_url = os.environ.get("QUOTE_API_URL", "https://dummyjson.com/quotes/random")
    resp = requests.get(quote_url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    quote = data.get("quote", "No quote available")
    author = data.get("author", "Unknown")
    return render(request, "tasks/inspiration.html", {"quote": quote, "author": author})


# --- JSON API (DRF) ---

@api_view(["GET", "POST"])
def api_tasks(request):
    if request.method == "GET":
        tasks = Task.objects.all()
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    json_data = request.data
    serializer = TaskSerializer(data=json_data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def api_task_detail(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    serializer = TaskSerializer(task)
    return Response(serializer.data)


@api_view(["GET"])
def api_analytics(request):
    analytics = TaskAnalytics()
    return Response(analytics.get_summary())


@api_view(["POST"])
def api_import_tasks(request):
    url = request.data.get("url")
    if not url:
        return Response({"error": "url is required"}, status=status.HTTP_400_BAD_REQUEST)
    max_items = request.data.get("max", 50)
    importer = ExternalTaskImporter(url)
    count = importer.fetch_and_import(max_items=max_items)
    return Response({"imported": count}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def api_sync_dashboard(request):
    analytics = TaskAnalytics()
    result = analytics.sync_to_dashboard()
    if result is None:
        return Response(
            {"error": "dashboard sync failed or not configured"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(result)
