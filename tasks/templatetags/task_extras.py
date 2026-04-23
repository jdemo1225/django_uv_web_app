from django import template
from django.utils.safestring import mark_safe

import requests

register = template.Library()


@register.filter
def priority_badge(priority):
    """Renders a colored badge span for a task priority."""
    colors = {
        "high": ("#fde8ec", "#e94560"),
        "medium": ("#fef5e0", "#d4940a"),
        "low": ("#e0f7f5", "#2da89a"),
    }
    bg, fg = colors.get(priority, ("#eee", "#555"))
    return mark_safe(
        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;'
        f'font-size:0.7rem;text-transform:uppercase;font-weight:600">{priority}</span>'
    )


@register.filter
def status_icon(status):
    """Returns a unicode icon for a task status."""
    icons = {
        "todo": "\u25cb",       # empty circle
        "in_progress": "\u25cf",  # filled circle
        "done": "\u2713",       # checkmark
    }
    return icons.get(status, "\u25cb")


@register.simple_tag
def external_quote():
    """Fetches a random quote from an external API for use in templates."""
    try:
        resp = requests.get("https://dummyjson.com/quotes/random", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        return f'"{data.get("quote", "")}" — {data.get("author", "Unknown")}'
    except requests.RequestException:
        return '"Stay focused." — Unknown'


@register.inclusion_tag("tasks/partials/task_card.html", takes_context=True)
def render_task_card(context, task):
    """Renders a single task card partial."""
    return {"task": task, "request": context.get("request")}
