"""Banco do Keycloak (k8s/sql_db.md inteiro, com interface).

1. Conexão: a do ambiente (``KEYCLOAK_DB_*``) ou outra escolhida aqui, guardada na sessão.
2. Restaurar dump: upload, restauração num banco temporário, conferência e troca.
3. Conexões ativas: quem está usando o banco (diagnóstico do "already exists").
4. Senha de um admin direto no banco, sem saber nenhuma senha.
5. Gerar um dump novo para baixar.

Não depende do Keycloak estar no ar: fala direto com o PostgreSQL.
"""
import shutil
import tempfile
from datetime import datetime
from os import environ
from pathlib import Path
from typing import Any

from django import forms
from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import redirect

from keycloak.automacao import dump as servico
from keycloak.automacao.plano import ATUALIZAR, CRIAR, OK, REMOVER, Passo
from keycloak.automacao.web import GRUPOS_EDICAO, exigir, pode
from keycloak.models import Aplicacao

CHAVE_SESSAO = "restaurar_dump"
SSLMODES = [(m, m) for m in ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")]


class ConexaoForm(forms.Form):
    # Ids próprios: a tela tem outro campo "senha" (o da seção 4)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, auto_id="conexao_%s", **kwargs)

    host = forms.CharField(label="Host", max_length=255)
    porta = forms.IntegerField(label="Porta", min_value=1, max_value=65535)
    usuario = forms.CharField(label="Usuário", max_length=100, help_text="Precisa poder criar, renomear e apagar bancos")
    senha = forms.CharField(label="Senha", required=False, widget=forms.PasswordInput,
                            help_text="Em branco: mantém a senha atual")
    nome = forms.CharField(label="Banco do Keycloak", max_length=63)
    administrativo = forms.CharField(label="Banco administrativo", max_length=63, help_text="postgres; no Akamai, defaultdb")
    sslmode = forms.ChoiceField(label="SSL", choices=SSLMODES, help_text="No Akamai, require")


class EnvioForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo do dump", help_text="Formato custom do PostgreSQL (pg_dump -Fc), ex.: keycloak.dump")


class ConfirmarForm(forms.Form):
    confirmacao = forms.CharField(label="Digite o nome do banco para confirmar", max_length=100)

    def __init__(self, *args, banco: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.banco = banco

    def clean_confirmacao(self) -> str:
        if self.cleaned_data["confirmacao"].strip() != self.banco:
            raise forms.ValidationError(f"Digite exatamente {self.banco}.")
        return self.banco


TrocaForm = ConfirmarForm


class SenhaForm(forms.Form):
    usuario = forms.ChoiceField(label="Admin do console (realm master)")
    senha = forms.CharField(label="Nova senha", min_length=4, widget=forms.PasswordInput)
    repetir = forms.CharField(label="Repita a senha", widget=forms.PasswordInput)

    def __init__(self, *args, usuarios: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].choices = [(u, u) for u in usuarios]

    def clean(self) -> dict:
        dados = super().clean()
        if dados.get("senha") and dados.get("senha") != dados.get("repetir"):
            self.add_error("repetir", "As senhas não conferem.")
        return dados


def view(context, request) -> dict[str, Any] | Any:
    banco = servico.Banco.da_sessao(request.session)
    padrao = servico.Banco.do_ambiente()
    context.update(
        {
            "banco": banco,
            "conexao_da_tela": request.session.get(servico.CHAVE_SESSAO) is not None,
            "pode_editar": pode(request, GRUPOS_EDICAO),
            "pode_reiniciar": servico.pode_reiniciar(),
            "comando_reiniciar": servico.comando_reiniciar(),
            "envio_form": EnvioForm(),
            "conexao_form": _form_conexao(banco or padrao),
        }
    )
    troca_form = ConfirmarForm(banco=banco.nome) if banco else None
    senha_form = None
    if request.method == "POST":
        if not exigir(request, GRUPOS_EDICAO):
            return redirect(request.path)
        acao = request.POST.get("acao")
        if acao == "conectar":
            form = ConexaoForm(request.POST)
            if form.is_valid() and _conectar(request, form.cleaned_data, banco):
                return redirect(request.path)
            context["conexao_form"] = form
        elif acao == "padrao":
            servico.Banco.esquecer(request.session)
            messages.info(request, "Voltou para a conexão do ambiente (KEYCLOAK_DB_*).")
            return redirect(request.path)
        elif banco is None:
            messages.error(request, "Configure a conexão com o banco primeiro.")
        elif acao == "enviar":
            envio_form = EnvioForm(request.POST, request.FILES)
            if envio_form.is_valid():
                _enviar(request, banco, envio_form.cleaned_data["arquivo"])
                return redirect(request.path)
            context["envio_form"] = envio_form
        elif acao == "trocar":
            troca_form = ConfirmarForm(request.POST, banco=banco.nome)
            if troca_form.is_valid():
                _trocar(request, banco)
                return redirect(request.path)
        elif acao == "descartar":
            _executar(request, banco, False, lambda: servico.descartar_temporario(banco),
                      [Passo(REMOVER, "banco", banco.temporario, "descartado sem trocar")])
            messages.info(request, f"Banco {banco.temporario} apagado. O Keycloak não foi tocado.")
            return redirect(request.path)
        elif acao == "senha":
            senha_form = _senha(request, banco)
            if senha_form is None:
                return redirect(request.path + "#senha")
        elif acao == "dump":
            resposta = _gerar_dump(request, banco)
            if resposta:
                return resposta
            return redirect(request.path + "#dump")

    if banco is None:
        return {"request": request, "context": context}
    context.update({"troca_form": troca_form, "envio": request.session.get(CHAVE_SESSAO)})
    try:
        context.update(_estado(banco))
        context["servidor"] = servico.testar(banco)
        context["conexoes"] = servico.conexoes(banco)
        usuarios = servico.usuarios_com_senha(banco) if context["atual"] else []
        context["senha_form"] = senha_form or SenhaForm(usuarios=usuarios)
    except servico.ErroDump as erro:
        context["erro"] = str(erro)
    return {"request": request, "context": context}


def _form_conexao(banco: "servico.Banco | None") -> ConexaoForm:
    if banco is None:
        return ConexaoForm(initial={"porta": 5432, "nome": "keycloak", "administrativo": "postgres", "sslmode": "prefer"})
    return ConexaoForm(initial={k: getattr(banco, k) for k in ("host", "porta", "usuario", "nome", "administrativo", "sslmode")})


def _conectar(request, dados: dict, atual: "servico.Banco | None") -> bool:
    """Testa a conexão nova antes de guardar; senha em branco mantém a atual."""
    senha = dados["senha"] or (atual.senha if atual else "")
    banco = servico.Banco(host=dados["host"].strip(), porta=str(dados["porta"]), usuario=dados["usuario"].strip(),
                          senha=senha, nome=dados["nome"].strip(), administrativo=dados["administrativo"].strip(),
                          sslmode=dados["sslmode"])
    try:
        info = servico.testar(banco)
    except servico.ErroDump as erro:
        messages.error(request, f"Nada foi salvo. {erro}")
        return False
    banco.guardar(request.session)
    messages.success(request, f"Conectado em {banco.descricao} (PostgreSQL {info['versao']}). Vale só para a sua sessão.")
    return True


def _senha(request, banco: servico.Banco) -> "SenhaForm | None":
    """Seção 4.3: grava o hash pbkdf2-sha256 direto no banco. Devolve o form com erros, ou None se gravou."""
    form = SenhaForm(request.POST, usuarios=servico.usuarios_com_senha(banco))
    if not form.is_valid():
        return form
    usuario = form.cleaned_data["usuario"]
    alterados: list[int] = []
    if _executar(request, banco, False, lambda: alterados.append(servico.trocar_senha(banco, usuario, form.cleaned_data["senha"])),
                 [Passo(ATUALIZAR, "senha", f"master/{usuario}", "pbkdf2-sha256 direto no banco")], realm="master"):
        if alterados and alterados[0]:
            messages.success(request, f"Senha de {usuario} trocada no banco.")
            _reiniciar(request, "para a senha nova valer (o cache ainda guarda a antiga)")
        else:
            messages.error(request, f"Nada mudou: {usuario} não existe no master ou não tem senha cadastrada.")
    return None


def _gerar_dump(request, banco: servico.Banco) -> "FileResponse | None":
    arquivo: list = []
    if not _executar(request, banco, False, lambda: arquivo.append(servico.gerar_dump(banco)),
                     [Passo(CRIAR, "dump", banco.nome, "pg_dump -Fc --no-owner --no-privileges")]):
        return None
    nome = f"{banco.nome}-{datetime.now():%Y-%m-%d_%H%M}.dump"
    return FileResponse(arquivo[0], as_attachment=True, filename=nome, content_type="application/octet-stream")


def _reiniciar(request, motivo: str) -> None:
    if servico.pode_reiniciar():
        try:
            servico.reiniciar_keycloak()
            messages.info(request, "Keycloak reiniciando. Em 1 a 2 minutos ele volta.")
        except servico.ErroDump as erro:
            messages.error(request, str(erro))
    else:
        messages.warning(request, f"Reinicie o Keycloak {motivo}: {servico.comando_reiniciar()}")


def _estado(banco: servico.Banco) -> dict[str, Any]:
    """O que existe agora no servidor: banco atual, temporário (se houver) e cópias antigas."""
    admin = environ.get("KEYCLOAK_ADMIN_USER", "")
    atual = servico.conferir(banco, banco.nome) if servico.existe(banco, banco.nome) else None
    novo = servico.conferir(banco, banco.temporario) if servico.existe(banco, banco.temporario) else None
    avisos, bloqueios = [], []
    if novo:
        bloqueios += novo.problemas
        avisos += novo.avisos
        if atual and atual.versao and novo.versao:
            if servico.versao_numerica(novo.versao) > servico.versao_numerica(atual.versao):
                bloqueios.append(
                    f"O dump é do Keycloak {novo.versao}, mais novo que o banco atual ({atual.versao}). "
                    "O Keycloak não volta versão: atualize a imagem antes."
                )
            elif servico.versao_numerica(novo.versao) < servico.versao_numerica(atual.versao):
                avisos.append(
                    f"O dump é do Keycloak {novo.versao} e o atual está em {atual.versao}: no reinício, o Keycloak "
                    "migra o schema (sem volta; a cópia de segurança continua na versão antiga)."
                )
        if admin and admin not in novo.admins_master:
            avisos.append(
                f"O usuário {admin} (KEYCLOAK_ADMIN_USER do assistente) não existe no master do dump: depois da troca, "
                "as outras telas não conseguem falar com a Admin API até você ajustar KEYCLOAK_ADMIN_USER/PASSWORD."
            )
        elif admin:
            avisos.append(
                f"O admin do console passa a ser o do dump. Se a senha de {admin} lá for outra, ajuste "
                "KEYCLOAK_ADMIN_PASSWORD do assistente (k8s/sql_db.md, seção 4)."
            )
        realms_perdidos = sorted(set(atual.realms) - set(novo.realms)) if atual else []
        if realms_perdidos:
            avisos.append(f"Realms do banco atual que não estão no dump (somem com a troca): {', '.join(realms_perdidos)}.")
    return {"atual": atual, "novo": novo, "copias": servico.copias(banco), "avisos": avisos, "bloqueios": bloqueios}


def _enviar(request, banco: servico.Banco, arquivo) -> None:
    """Grava o upload num arquivo temporário, confere o formato e restaura em ``<banco>_new``."""
    pasta = Path(tempfile.mkdtemp(prefix="dump-"))
    caminho = pasta / "keycloak.dump"
    try:
        with caminho.open("wb") as destino:
            for pedaco in arquivo.chunks():
                destino.write(pedaco)
        info = servico.listar(str(caminho))
        if not info.tem_keycloak:
            raise servico.ErroDump("O dump não tem a tabela migration_model: não é um banco do Keycloak.")
        erros: list[str] = []
        passos = [
            Passo(REMOVER if servico.existe(banco, banco.temporario) else OK, "banco", banco.temporario, "recriado vazio"),
            Passo(CRIAR, "restauração", arquivo.name, f"{info.objetos} objetos · {_tamanho(arquivo.size)}"),
        ]
        if not _executar(request, banco, True, lambda: erros.extend(servico.restaurar_temporario(banco, str(caminho))),
                         passos, erro_extra=lambda: "\n".join(erros)):
            return
    except servico.ErroDump as erro:
        messages.error(request, str(erro))
        return
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    request.session[CHAVE_SESSAO] = {
        "nome": arquivo.name,
        "tamanho": _tamanho(arquivo.size),
        "criado": info.cabecalho.get("Archive created at", ""),
        "origem": info.cabecalho.get("dbname", ""),
        "servidor": info.cabecalho.get("Dumped from database version", "").split(" ")[0],
        "erros": erros,
    }
    if erros:
        messages.error(request, f"O pg_restore relatou {len(erros)} erro(s). Confira abaixo antes de trocar.")
    else:
        messages.success(request, f"Dump restaurado em {banco.temporario}. Confira os realms e troque os bancos.")


def _trocar(request, banco: servico.Banco) -> None:
    estado = _estado(banco)
    if not estado["novo"]:
        messages.error(request, f"Não há banco {banco.temporario}: envie o dump de novo.")
        return
    if estado["bloqueios"]:
        messages.error(request, "Troca recusada: " + " ".join(estado["bloqueios"]))
        return
    copia: list[str] = []
    passos = [
        Passo(ATUALIZAR, "banco", banco.nome, "vira cópia de segurança (sem conexões)"),
        Passo(ATUALIZAR, "banco", banco.temporario, f"passa a se chamar {banco.nome}"),
    ]
    if not _executar(request, banco, False, lambda: copia.append(servico.trocar(banco)), passos):
        return
    request.session.pop(CHAVE_SESSAO, None)
    messages.success(request, f"Bancos trocados. Cópia do anterior: {copia[0] or '(não havia banco)'}.")
    _reiniciar(request, "para ele largar o cache antigo")


def _executar(request, banco: servico.Banco, simulacao: bool, acao, passos: list[Passo], erro_extra=lambda: "",
              realm: str = "") -> bool:
    """Roda a ação e guarda no histórico (``simulacao`` = só mexeu no banco temporário)."""
    registro = Aplicacao(usuario=request.user, servidor=banco.descricao, realm=realm or banco.nome, etapa=Aplicacao.DUMP,
                         simulacao=simulacao, passos=[p.__dict__ for p in passos],
                         mudancas=sum(1 for p in passos if p.situacao != OK))
    try:
        acao()
    except servico.ErroDump as erro:
        registro.sucesso, registro.erro = False, str(erro)
        registro.save()
        messages.error(request, str(erro))
        return False
    registro.erro = erro_extra()
    registro.sucesso = not registro.erro
    registro.save()
    return True


def _tamanho(n: int) -> str:
    for unidade in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"
