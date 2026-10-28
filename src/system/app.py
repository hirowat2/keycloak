from django.urls import path

from commercial.propostas.empresas import trocar_empresa

from . import views
from .sso import external_login_required

urlpatterns = [
    path("", views.index, name="index"),
    path("empresa/", external_login_required(trocar_empresa), name="trocar_empresa"),
    path("<str:page>/", views.page, name="page"),
]
