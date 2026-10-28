from django.urls import path

from system.sso import auth_complete

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login", views.login, name="login"),
    path("auth/complete/", auth_complete, name="auth"),
    path("logout", views.logout, name="logout"),
]
