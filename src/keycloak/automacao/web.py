"""Utilitários compartilhados pelas telas do sistema."""

from functools import wraps
from os import environ
from typing import Callable

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from keycloak.models import Aplicacao
from keycloak.screens.config.permissions import user_in_groups

from . import servidores
from .api import ErroKeycloak, KeycloakAdmin, ativo, conexao, usar
from .plano import Plano
from .realm import listar_realms

GRUPOS_CONSULTA = ["Admin", "Limited"]
GRUPOS_EDICAO = ["Admin"]

CHAVE_REALMS = "keycloak:realms"
_api: KeycloakAdmin | None = None


def api() -> KeycloakAdmin:
    """O Keycloak escolhido no menu; sem cadastro, o do ambiente (uma conexão por processo)."""
    if (cliente := ativo()) is not None:
        return cliente
    global _api
    if _api is None:
        _api = conexao()
    return _api


def _chave_realms() -> str:
    return f"{CHAVE_REALMS}:{api().url}"


def realms_disponiveis() -> list[str]:
    """Realms que o assistente configura (o master fica de fora: é o do console)."""
    chave = _chave_realms()
    nomes = cache.get(chave)
    if nomes is None:
        nomes = sorted(r["realm"] for r in listar_realms(api()) if r["realm"] != "master")
        cache.set(chave, nomes, 30)
    return nomes


def esquecer_realms() -> None:
    cache.delete(_chave_realms())


class KeycloakAtivoMiddleware:
    """Ativa, em cada requisição, o Keycloak escolhido no menu (tela Servidores)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.keycloak = None
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            request.keycloak = servidores.ativar(request.session)
        try:
            return self.get_response(request)
        finally:
            usar(None)  # a thread atende outra requisição em seguida


def realm_ativo(request, realms: list[str]) -> str | None:
    """O realm escolhido no menu; sem escolha, o do login do assistente ou o primeiro."""
    for candidato in (request.session.get("realm"), environ.get("KEYCLOAK_REALM")):
        if candidato in realms:
            return candidato
    return realms[0] if realms else None


def pode(request, grupos: list[str]) -> bool:
    return user_in_groups(request.user, grupos)


def exigir(request, grupos: list[str]) -> bool:
    """True se o usuário pode; senão registra a mensagem de erro."""
    if pode(request, grupos):
        return True
    messages.error(request, "Só administradores (role ADMIN) aplicam mudanças no Keycloak. Peça a um deles.")
    return False


def com_realm(exige_realm: bool = True):
    """Tela do sistema: recebe o realm ativo e mostra um aviso se o Keycloak não responder.

    Os formulários enviam o realm em que foram abertos (``realm_tela``). O realm
    ativo fica na sessão, comum a todas as abas: se ele mudou em outra aba, a
    ação é recusada em vez de cair no realm errado.
    """

    def decorador(view):
        @wraps(view)
        def envolvida(context, request):
            try:
                realms = realms_disponiveis()
                realm = realm_ativo(request, realms)
                if exige_realm and realm is None:
                    return render(request, "sem_realm.html", context)
                if request.method == "POST" and exige_realm and request.POST.get("realm_tela") != realm:
                    messages.error(request, f"O realm ativo mudou para {realm} em outra aba. Nada foi feito; confira a tela e repita a ação.")
                    return redirect(request.get_full_path())
                context.update({"realm": realm, "realms": realms, "pode_editar": pode(request, GRUPOS_EDICAO)})
                return view(context, request, realm)
            except ErroKeycloak as erro:
                context["erro"] = str(erro)
                context["servidor"] = api().url
                return render(request, "sem_conexao.html", context, status=502)

        return envolvida

    return decorador


def simulando(request) -> bool:
    """Os formulários têm dois botões: "Simular" (padrão) e "Aplicar" (``acao=aplicar``)."""
    return request.POST.get("acao") != "aplicar"


def executar(request, realm: str, etapa: str, funcao: Callable[[bool], Plano]) -> Plano | None:
    """Roda a etapa (simulação ou aplicação), guarda no histórico e avisa o resultado."""
    simular = simulando(request)
    if not simular and not exigir(request, GRUPOS_EDICAO):
        return None
    registro = Aplicacao(usuario=request.user, servidor=api().url, realm=realm, etapa=etapa, simulacao=simular)
    try:
        plano = funcao(simular)
    except (ErroKeycloak, ValueError) as erro:
        registro.sucesso, registro.erro = False, str(erro)
        registro.save()
        aviso = "" if simular else " O que já foi feito fica; aplicar de novo continua de onde parou."
        messages.error(request, f"{erro}{aviso}")
        return None
    registro.mudancas, registro.passos = plano.mudancas, plano.como_lista()
    registro.save()
    if etapa == Aplicacao.REALM:
        esquecer_realms()
    if simular:
        messages.info(request, f"Simulação: {plano.mudancas} mudança(s). Nada foi gravado; confira e clique em Aplicar.")
    elif plano.mudancas:
        messages.success(request, f"Aplicado no Keycloak: {plano.mudancas} mudança(s).")
    else:
        messages.info(request, "Nada a mudar: o Keycloak já está como pedido.")
    return plano


def trocar_servidor(request):
    """Troca o Keycloak ativo (seletor do menu lateral). O realm volta ao padrão do novo servidor."""
    destino = request.POST.get("next") or "/app/"
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = "/app/"
    if request.method == "POST":
        chave = request.POST.get("servidor")
        alvo = next((a for a in servidores.disponiveis() if a.chave == chave), None)
        if alvo is not None and request.session.get(servidores.CHAVE_SESSAO) != chave:
            request.session[servidores.CHAVE_SESSAO] = chave
            request.session.pop("realm", None)
            messages.info(request, f"Keycloak ativo: {alvo.nome} ({alvo.url}).")
    return redirect(destino)


def trocar_realm(request):
    """Troca o realm ativo (seletor do menu lateral) e volta para a mesma tela."""
    destino = request.POST.get("next") or "/app/"
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = "/app/"
    if request.method == "POST":
        try:
            realms = realms_disponiveis()
        except ErroKeycloak as erro:
            messages.error(request, str(erro))
            return redirect(destino)
        if request.POST.get("realm") in realms:
            request.session["realm"] = request.POST["realm"]
    return redirect(destino)
