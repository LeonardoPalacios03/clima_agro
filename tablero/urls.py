from django.urls import path

from . import views

urlpatterns = [
    path("", views.vista_general, name="general"),
    path("detalle/", views.vista_detalle, name="detalle"),
]
