"""Login pelo Keycloak e lista de e-mails que podem entrar.

O ``keycloak.js`` grava o token de acesso no cookie ``SSOToken``; aqui ele é
validado (assinatura do realm, emissor, client e validade) e o e-mail, o nome e
os papéis saem do token, nunca de cookies avulsos. Só entram os e-mails de
``EMAILS_PERMITIDOS`` (ver ``documents/controle_de_acesso.md``).
"""

from functools import lru_cache, wraps
from os import environ
from urllib.parse import unquote, urlencode

import jwt
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.models import Group, User
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

SEM_PERMISSAO = "O e-mail {email} não tem acesso a este sistema. Peça a liberação ao administrador."


# Únicos e-mails que entram pelo Keycloak no deploy (em minúsculas). Fixo no código de propósito:
# liberar outra pessoa exige mudar esta lista e publicar uma nova versão.
EMAILS_PERMITIDOS = frozenset(
    {
        "leao@estatcamp.com.br",  # Dorival Leão
        "hiro@estatcamp.com.br",  # Hiro Watanabe
        "lucas@estatcamp.com.br",  # Lucas Farias
        "rubens@estatcamp.com.br",  # Rubens
        "victor@estatcamp.com.br",  # Victor Vasconcelos
        "vitor@estatcamp.com.br",  # Vitor Cezareto
    }
)


# Usuário "admin" do realm local (data/keycloak/realm); entra só com DEBUG ligado, como no docker-compose.
EMAIL_ADMIN_LOCAL = "local-admin@mail.com"


def email_permitido(email: str) -> bool:
    email = email.strip().lower()
    return email in EMAILS_PERMITIDOS or (settings.DEBUG and email == EMAIL_ADMIN_LOCAL)


def _emissor() -> str:
    return f"{environ.get('KEYCLOAK_HOST', '').rstrip('/')}/realms/{environ.get('KEYCLOAK_REALM', '')}"


@lru_cache(maxsize=1)
def _chaves(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url)


def _chave_publica(token: str):
    """Chave do realm que assinou o token. Dentro do Docker o Keycloak é buscado
    pelo endereço interno (KEYCLOAK_INTERNAL_URL), se houver."""
    base = environ.get("KEYCLOAK_INTERNAL_URL") or environ.get("KEYCLOAK_HOST", "")
    url = f"{base.rstrip('/')}/realms/{environ.get('KEYCLOAK_REALM', '')}/protocol/openid-connect/certs"
    return _chaves(url).get_signing_key_from_jwt(token).key


def claims_do_token(token: str) -> dict:
    """Conteúdo do token de acesso, se ele for válido para este client; senão, jwt.InvalidTokenError."""
    claims = jwt.decode(
        token,
        _chave_publica(token),
        algorithms=["RS256"],
        issuer=_emissor(),
        options={"verify_aud": False, "require": ["exp", "iss"]},  # o aud do Keycloak é "account"
    )
    if claims.get("azp") != environ.get("KEYCLOAK_CLIENT_ID"):
        raise jwt.InvalidTokenError("Token emitido para outro client.")
    return claims


class EmailPermitidoMiddleware:
    """Encerra a sessão de quem entrou pelo Keycloak e saiu da lista de e-mails.

    Vale só para contas do login corporativo (sem senha no Django); o
    superusuário local do /admin/ não passa por aqui.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_superuser
            and not user.has_usable_password()
            and not email_permitido(user.email)
        ):
            email = user.email
            logout(request)
            return HttpResponseForbidden(SEM_PERMISSAO.format(email=email))
        return self.get_response(request)



def create_default_groups(
    group_names: list[str],
):
    for name in group_names:
        Group.objects.get_or_create(name=name)


def external_login_required(
    view_func,
):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)

        # A rota de login é "/login" (sem barra); "/login/" dava 404.
        return redirect(f"{reverse('login')}?{urlencode({'next': request.get_full_path()})}")

    return wrapper


def auth_complete(
    request: HttpRequest,
):
    allowedGroups = [
        "Admin",
        "Master",
        "Tech",
        "Limited",
        "Missing",
    ]
    create_default_groups(allowedGroups)

    try:
        claims = claims_do_token(unquote(request.COOKIES.get("SSOToken", "").strip()))
    except jwt.PyJWKClientError:
        return HttpResponseBadRequest("Não foi possível falar com o Keycloak para conferir o login. Tente de novo.")
    except jwt.InvalidTokenError:
        return HttpResponseBadRequest("Login inválido ou expirado. Feche o navegador e entre de novo.")

    email = (claims.get("email") or "").strip()
    name = (claims.get("name") or claims.get("preferred_username") or "").strip()
    groups = [g.strip().lower() for g in claims.get("resource_access", {}).get("account", {}).get("roles", [])]
    defaultUser = "Master"

    if not email or not name:
        return HttpResponseBadRequest(
            "Please, close your browser then try it again",
        )

    if not email_permitido(email):
        return HttpResponseForbidden(SEM_PERMISSAO.format(email=email))

    validGroups = [g.capitalize() for g in groups if g.capitalize() in allowedGroups]
    userGroups = [defaultUser] if not len(validGroups) else validGroups
    djangoGroups = Group.objects.filter(name__in=userGroups)
    # A conta é a do e-mail (a lista de acesso é por e-mail); o nome só batiza contas novas.
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        username = email if User.objects.filter(username=name).exists() else name
        user = User.objects.create(username=username, email=email)

    user.set_unusable_password()
    user.groups.set(djangoGroups)
    user.save()

    login(request, user)

    return redirect(
        request.GET.get(
            "next",
            "/",
        )
    )