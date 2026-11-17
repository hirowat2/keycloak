"""Servidores: os Keycloaks que o assistente administra, cadastrados pela interface.

Cada cadastro guarda a URL pública (a que o navegador e o SSO enxergam), a URL
interna opcional (por onde o assistente chama a Admin API) e a credencial do
realm master: usuário e senha do admin ou um client com service account. A
senha/secret fica cifrada no banco do assistente.

O escolhido no seletor do menu vale para a sessão de quem escolheu. O login no
assistente não muda: continua no Keycloak do ambiente (``KEYCLOAK_HOST``).
"""
from typing import Any
from urllib.parse import urlsplit

from django import forms
from django.contrib import messages
from django.shortcuts import redirect

from keycloak.automacao import servidores as servico
from keycloak.automacao.api import ErroKeycloak
from keycloak.automacao.web import GRUPOS_CONSULTA, GRUPOS_EDICAO, esquecer_realms, exigir, pode
from keycloak.models import Servidor

AUTENTICACOES = [
    ("senha", "Usuário e senha do admin do master"),
    ("client", "Client com service account (client credentials)"),
]


class ServidorForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=100, help_text="Como aparece no menu, ex.: Produção actionstat")
    url = forms.CharField(label="URL pública", max_length=255,
                         help_text="A raiz do Keycloak, ex.: https://keycloak.actionstat.app (com /auth se ele usar esse caminho)")
    url_interna = forms.CharField(label="URL interna (opcional)", max_length=255, required=False,
                                 help_text="Por onde o assistente chama a Admin API, se for outra. Ex.: http://keycloak.keycloak.svc:8080")
    autenticacao = forms.ChoiceField(label="Autenticação", choices=AUTENTICACOES, widget=forms.RadioSelect, initial="senha")
    usuario = forms.CharField(label="Usuário do admin (realm master)", max_length=150, required=False)
    client_id = forms.CharField(label="Client ID (realm master)", max_length=150, required=False, initial="admin-cli",
                                help_text="Só com service account: client confidential com a role admin do master")
    segredo = forms.CharField(label="Senha ou secret", required=False, widget=forms.PasswordInput,
                              help_text="Fica cifrada. Ao editar, em branco mantém a atual")
    verificar_tls = forms.BooleanField(label="Verificar o certificado TLS", required=False, initial=True,
                                       help_text="Desmarque só para certificado autoassinado em teste")

    def __init__(self, *args, instancia: Servidor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instancia = instancia

    def clean_nome(self) -> str:
        nome = self.cleaned_data["nome"].strip()
        repetido = Servidor.objects.filter(nome__iexact=nome)
        if self.instancia:
            repetido = repetido.exclude(pk=self.instancia.pk)
        if repetido.exists() or nome.lower() == "do ambiente":
            raise forms.ValidationError("Já existe um servidor com esse nome.")
        return nome

    def _url(self, campo: str) -> str:
        # Sem o URLValidator do Django: ele recusa host sem domínio, como o http://keycloak:8080 do compose
        valor = (self.cleaned_data.get(campo) or "").strip().rstrip("/")
        partes = urlsplit(valor)
        try:
            partes.port
        except ValueError:
            raise forms.ValidationError("Porta inválida.") from None
        if valor and (partes.scheme not in ("http", "https") or not partes.hostname or partes.username
                      or partes.query or partes.fragment or " " in valor):
            raise forms.ValidationError("Use http(s)://host[:porta][/caminho], sem usuário, ? nem #.")
        if valor.endswith(("/admin", "/realms/master")):
            raise forms.ValidationError("Use a raiz do Keycloak, sem /admin nem /realms/...")
        return valor

    def clean_url(self) -> str:
        return self._url("url")

    def clean_url_interna(self) -> str:
        return self._url("url_interna")

    def clean(self) -> dict:
        dados = super().clean()
        client = dados.get("autenticacao") == "client"
        if client and not dados.get("client_id"):
            self.add_error("client_id", "Informe o client da service account.")
        if not client and not dados.get("usuario"):
            self.add_error("usuario", "Informe o admin do realm master.")
        if not dados.get("segredo") and not (self.instancia and self.instancia.segredo
                                             and self.instancia.usa_client == client):
            self.add_error("segredo", "Informe a senha ou o secret.")
        return dados

    def preencher(self, servidor: Servidor) -> Servidor:
        dados = self.cleaned_data
        servidor.nome, servidor.url, servidor.url_interna = dados["nome"], dados["url"], dados["url_interna"]
        servidor.usa_client = dados["autenticacao"] == "client"
        servidor.usuario = "" if servidor.usa_client else dados["usuario"]
        servidor.client_id = (dados["client_id"] or "admin-cli") if servidor.usa_client else "admin-cli"
        servidor.verificar_tls = dados["verificar_tls"]
        if dados["segredo"]:
            servidor.segredo = servico.cifrar(dados["segredo"])
        return servidor


def _inicial(servidor: Servidor) -> dict:
    return {
        "nome": servidor.nome, "url": servidor.url, "url_interna": servidor.url_interna,
        "autenticacao": "client" if servidor.usa_client else "senha", "usuario": servidor.usuario,
        "client_id": servidor.client_id, "verificar_tls": servidor.verificar_tls,
    }


def _resumo_teste(alvo: servico.Alvo, resultado: dict) -> str:
    realms = resultado["realms"]
    lista = ", ".join(realms[:8]) + ("…" if len(realms) > 8 else "")
    return f"{alvo.nome}: Keycloak {resultado['versao'] or '?'} em {alvo.endereco_api}, {len(realms)} realm(s): {lista}."


def _usar(request, chave: str) -> None:
    request.session[servico.CHAVE_SESSAO] = chave
    request.session.pop("realm", None)


def _salvar(request, form: ServidorForm, testar: bool):
    servidor = form.preencher(form.instancia or Servidor(criado_por=request.user))
    if testar:
        alvo = servico.do_cadastro(servidor)
        try:
            resultado = servico.testar(alvo)
        except ErroKeycloak as erro:
            form.add_error(None, f"O Keycloak não aceitou a conexão: {erro}")
            return None
        messages.success(request, "Conexão ok. " + _resumo_teste(alvo, resultado))
    novo = servidor.pk is None
    servidor.save()
    servico.esquecer(str(servidor.pk))
    if novo:
        _usar(request, str(servidor.pk))
        messages.success(request, f"{servidor.nome} cadastrado e escolhido como o Keycloak ativo da sua sessão.")
    else:
        messages.success(request, f"{servidor.nome} atualizado.")
        if request.session.get(servico.CHAVE_SESSAO) == str(servidor.pk):
            esquecer_realms()
    return redirect(request.path)


def view(context, request) -> dict[str, Any] | Any:
    if not exigir(request, GRUPOS_CONSULTA):
        context["sem_acesso"] = True
        return {"request": request, "context": context}
    editar = request.GET.get("editar") or request.POST.get("editar") or ""
    instancia = Servidor.objects.filter(pk=editar).first() if editar.isdigit() else None
    form = ServidorForm(instancia=instancia, initial=_inicial(instancia) if instancia else None)

    if request.method == "POST":
        acao = request.POST.get("acao", "")
        if acao == "usar":
            alvo = next((a for a in servico.disponiveis() if a.chave == request.POST.get("chave")), None)
            if alvo:
                _usar(request, alvo.chave)
                messages.info(request, f"Keycloak ativo: {alvo.nome} ({alvo.url}).")
                return redirect("/app/painel/")
            return redirect(request.path)
        if acao == "testar_existente":
            alvo = next((a for a in servico.disponiveis() if a.chave == request.POST.get("chave")), None)
            if alvo:
                try:
                    messages.success(request, "Conexão ok. " + _resumo_teste(alvo, servico.testar(alvo)))
                except ErroKeycloak as erro:
                    messages.error(request, f"{alvo.nome}: {erro}")
            return redirect(request.path)
        if not exigir(request, GRUPOS_EDICAO):
            return redirect(request.path)
        if acao == "remover":
            servidor = Servidor.objects.filter(pk=request.POST.get("chave", "")).first() if request.POST.get("chave", "").isdigit() else None
            if servidor:
                servico.esquecer(str(servidor.pk))
                if request.session.get(servico.CHAVE_SESSAO) == str(servidor.pk):
                    request.session.pop(servico.CHAVE_SESSAO, None)
                    request.session.pop("realm", None)
                servidor.delete()
                messages.success(request, f"{servidor.nome} removido do assistente (nada muda no Keycloak dele).")
            return redirect(request.path)
        form = ServidorForm(request.POST, instancia=instancia)
        if form.is_valid():
            if acao == "testar":
                alvo = servico.do_cadastro(form.preencher(Servidor(segredo=instancia.segredo if instancia else "")))
                try:
                    context["teste"] = {"ok": True, "texto": _resumo_teste(alvo, servico.testar(alvo))}
                except ErroKeycloak as erro:
                    context["teste"] = {"ok": False, "texto": str(erro)}
            elif acao in ("salvar", "salvar_sem_testar"):
                resposta = _salvar(request, form, testar=acao == "salvar")
                if resposta is not None:
                    return resposta
                context["falhou_teste"] = True

    ativo = getattr(request, "keycloak", None)
    context.update(
        {
            "form": form,
            "editando": instancia,
            "servidores": servico.disponiveis(),
            "cadastros": {str(s.pk): s for s in Servidor.objects.select_related("criado_por")},
            "ativo": ativo.chave if ativo else "",
            "pode_editar": pode(request, GRUPOS_EDICAO),
        }
    )
    return {"request": request, "context": context}
