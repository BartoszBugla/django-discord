from django.urls import path
from . import views

app_name = "ankiety"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pytanie_id>/", views.szczegoly, name="szczegoly"),
]
