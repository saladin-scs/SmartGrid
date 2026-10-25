from django.urls import path

from . import views

app_name = "source_production"

urlpatterns = [
    path("", views.index, name="list"),
    path("create/", views.create, name="create"),
    path("i/<slug:local_name>/", views.detail, name="detail"),
    path("i/<slug:local_name>/edit/", views.edit, name="edit"),
    path("i/<slug:local_name>/delete/", views.delete, name="delete"),
]
