import importlib
import os
import sys
from typing import Any
from urllib.parse import urlencode

from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
)
from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.urls import reverse
from django.views.static import serve
from django.template import loader
from suspense.shortcuts import render

from system.sso import external_login_required


def media(request: HttpRequest, path: str) -> HttpResponseBase:
    """Arquivos de /media/ (o ``static()`` do Django só os serve com DEBUG ligado).

    Os do layout (css/, js/ e as imagens da raiz, usadas também no login) são
    públicos; os enviados pelos usuários (em subpastas) exigem login.
    """
    publico = path.startswith(("css/", "js/")) or "/" not in path
    if not publico and not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?{urlencode({'next': request.get_full_path()})}")
    return serve(request, path, document_root=settings.MEDIA_ROOT)


def landing(_: Any) -> HttpResponse:
    return HttpResponse(loader.get_template("landing.html").render())


@external_login_required
def index(request) -> HttpResponse:
    context = {"username": request.user}

    return HttpResponse(loader.get_template("index.html").render(context, request))


@external_login_required
def page(request, page: str) -> HttpResponse:
    context = {
        "username": request.user,
    }
    template = "index.html"
    view_result = {"context": {}}

    projectName = os.environ["PROJECT_PACKAGE_NAME"]
    projectPath = os.environ["PROJECT_PACKAGE_PATH"]

    sys.path.append(os.path.abspath(projectPath))

    page_name = page.strip("/")

    screens_path = os.path.join(projectPath, "screens")
    available_screens = [
        screen
        for screen in os.listdir(screens_path)
        # Só pastas com view.py são telas (config/ guarda o menu e as permissões).
        if os.path.isfile(os.path.join(screens_path, screen, "view.py"))
    ]

    matched_screen = None

    for screen in available_screens:
        if screen == page_name:
            matched_screen = screen
            break

    if matched_screen is None:
        raise Http404("Página não encontrada.")

    module = importlib.import_module(f"{projectName}.screens.{matched_screen}.view")
    view_result = module.view(context, request)
    template = f"{matched_screen}.html"

    if isinstance(view_result, HttpResponseBase):
        return view_result

    is_ajax = (
        request.method == "POST"
        and request.headers.get("X-Requested-With") == "XMLHttpRequest"
        and request.content_type == "application/json"
    )
    if is_ajax and "_ajax_response" in view_result["context"]:
        return JsonResponse(view_result["context"]["_ajax_response"])

    context.update(view_result["context"])
    return HttpResponse(render(request, template, context))


def login(
    request: HttpRequest,
) -> HttpResponse:
    template = loader.get_template("login.html")

    context = {
        "KEYCLOAK_REALM": os.environ.get("KEYCLOAK_REALM"),
        "KEYCLOAK_CLIENT_ID": os.environ.get("KEYCLOAK_CLIENT_ID"),
        "KEYCLOAK_HOST": os.environ.get("KEYCLOAK_HOST"),
    }

    return HttpResponse(template.render(context, request))


@external_login_required
def logout(
    request: HttpRequest,
) -> HttpResponse:
    # Encerra a sessão do Django. (Antes chamava a si mesma: recursão infinita.)
    auth_logout(request)

    return redirect("/")
