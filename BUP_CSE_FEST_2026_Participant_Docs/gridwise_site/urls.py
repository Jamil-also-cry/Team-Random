"""Root URL configuration. Delegates everything to the api app."""
from django.urls import path, include


urlpatterns = [
    path("", include("api.urls")),
]
