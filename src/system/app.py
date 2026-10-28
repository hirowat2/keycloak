from django.urls import path

from keycloak.automacao.web import trocar_realm

from . import views
from .sso import external_login_required

urlpatterns = [
    path("", views.index, name="index"),
    path("realm-ativo/", external_login_required(trocar_realm), name="trocar_realm"),
    path("<str:page>/", views.page, name="page"),
]
