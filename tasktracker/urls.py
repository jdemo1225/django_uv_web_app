from django.conf.urls import url, include
from django.contrib import admin

# django.conf.urls.url() was deprecated in Django 4.0 and REMOVED in 4.2.
# A major upgrade to Django 5.x must switch these routes to path()/re_path().
urlpatterns = [
    url(r"^admin/", admin.site.urls),
    url(r"^", include("tasks.urls")),
]
