from django.conf.urls import url

from . import views

# django.conf.urls.url() was deprecated in Django 4.0 and REMOVED in 4.2.
# All entries below must be converted to path()/re_path() when upgrading
# past Django 4.2 — note the <int:task_id> converters have to be
# reintroduced (they were dropped to get regex named groups here).
urlpatterns = [
    url(r"^$", views.index, name="index"),
    url(r"^add/$", views.add_task, name="add_task"),
    url(r"^edit/(?P<task_id>\d+)/$", views.edit_task, name="edit_task"),
    url(r"^toggle/(?P<task_id>\d+)/$", views.toggle_task, name="toggle_task"),
    url(r"^delete/(?P<task_id>\d+)/$", views.delete_task, name="delete_task"),
    url(r"^stats/$", views.stats, name="stats"),
    url(r"^inspiration/$", views.inspiration, name="inspiration"),
    url(r"^api/tasks/$", views.api_tasks, name="api_tasks"),
    url(r"^api/tasks/(?P<task_id>\d+)/$", views.api_task_detail, name="api_task_detail"),
    url(r"^api/analytics/$", views.api_analytics, name="api_analytics"),
    url(r"^api/import/$", views.api_import_tasks, name="api_import_tasks"),
    url(r"^api/sync-dashboard/$", views.api_sync_dashboard, name="api_sync_dashboard"),
]
