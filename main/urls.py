from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("mood/", views.mood, name="mood"),
    path("results/", views.results, name="results"),
    path("accounts/register/", views.register, name="register"),
]
