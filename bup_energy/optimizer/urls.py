from django.urls import path

from . import views

urlpatterns = [
    path("optimize-energy", views.optimize_energy_view, name="optimize-energy"),
]