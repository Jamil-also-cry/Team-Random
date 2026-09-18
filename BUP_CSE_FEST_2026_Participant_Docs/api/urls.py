"""URL routes exposed by the api app. Mirrors the FastAPI app's routes 1:1."""
from django.urls import path
from . import views


urlpatterns = [
    path("health", views.HealthView.as_view(), name="health"),
    path("optimize-energy", views.OptimizeEnergyView.as_view(), name="optimize-energy"),
]
