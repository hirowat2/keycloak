from django.urls import path

from keycloak.automacao.web import trocar_realm, trocar_servidor

from . import views
from .sso import external_login_required

urlpatterns = [
    path("", views.index, name="index"),
    path("realm-ativo/", external_login_required(trocar_realm), name="trocar_realm"),
    path("servidor-ativo/", external_login_required(trocar_servidor), name="trocar_servidor"),
    path("<str:page>/", views.page, name="page"),
]
