"""Guia do Azure AD (Microsoft Entra ID): o que fazer no portal do Azure, com os valores do realm ativo.

É a seção 2.2 e a seção 4 do README_sso.md em forma de tela: as URLs, os
claims e os grupos já vêm preenchidos com o realm, o alias e os grupos da
etapa 2, e há um texto pronto para mandar ao time do Azure. Não muda nada no
Keycloak; o cadastro do provedor é a etapa 3 e o mapeamento, a etapa 4.
"""
from typing import Any

from django.utils.html import escape
from django.utils.safestring import mark_safe

from keycloak.automacao import saml as servico
from keycloak.automacao.api import url_publica
from keycloak.automacao.grupos import ler_grupos
from keycloak.automacao.web import api, com_realm

# O que o Keycloak lê de cada claim (mappers da etapa 3) e de onde o Entra tira o valor.
CLAIMS = [
    ("givenname", f"{servico.CLAIMS_ENTRA}givenname", "user.givenname", "nome"),
    ("surname", f"{servico.CLAIMS_ENTRA}surname", "user.surname", "sobrenome"),
    ("emailaddress", f"{servico.CLAIMS_ENTRA}emailaddress", "user.mail", "e-mail do usuário; também vira o username"),
    ("name", f"{servico.CLAIMS_ENTRA}name", "user.userprincipalname", "não é lido pelo Keycloak; deixe como está"),
    ("Identificador Exclusivo do Usuário (ID de Nome)", "NameID", "user.userprincipalname", "identificador do login (formato e-mail)"),
    ("groups", "groups", "user.groups", "grupos atribuídos ao app (passo 7); viram grupos na etapa 4"),
]

# Erros que o Entra mostra na tela de login (código AADSTS) e no Keycloak, com a correção.
ERROS = [
    ("AADSTS700016", "Application with identifier '…' was not found in the directory",
     "O Identifier (Entity ID) do app no Azure é diferente do Entity ID do Keycloak. Copie de novo o valor do passo 2 (sem barra no fim)."),
    ("AADSTS50011", "The reply URL specified in the request does not match",
     "A Reply URL no Azure não é a do alias usado. Confira o alias: ele faz parte da URL (…/broker/<alias>/endpoint)."),
    ("AADSTS50105", "The signed in user is not assigned to a role for the application",
     "Assignment required = Yes e o usuário não está em nenhum grupo atribuído ao app. Coloque-o no grupo (passo 4) ou atribua o grupo (passo 5)."),
    ("AADSTS75011", "Authentication method by which the user authenticated doesn't match",
     "O Keycloak pediu um método de autenticação específico. Em Identity providers → <alias>, deixe Requested AuthnContext vazio."),
    ("AADSTS90072", "User account from identity provider does not exist in tenant",
     "Usuário convidado (B2B) que ainda não aceitou o convite, ou de outro tenant. Convide-o em Users → Invite external user."),
    ("Invalid signature (Keycloak)", "Erro no Keycloak depois do login no Azure",
     "O Azure trocou o certificado de assinatura. Na etapa 3, clique em Aplicar de novo com a mesma URL de metadata: o Keycloak relê o certificado."),
    ("Invalid requester / sem e-mail (Keycloak)", "O usuário entra mas fica sem e-mail ou cai em 'Update account information'",
     "O usuário não tem o campo Email preenchido no Entra (comum em convidados). Preencha o Email no Entra, ou use user.userprincipalname no claim emailaddress."),
    ("Entra mas sem acesso no app", "Login funciona, mas o app diz acesso negado",
     "O claim de grupos não chegou ou o mapper não bate. Veja em Conferir o usuário e os grupos; confira Source attribute e o nome customizado groups (passo 3)."),
]


def _c(valor: str) -> str:
    """Valor para copiar dentro do texto do passo (escapado: o nome do app vem da URL)."""
    return f'<code class="ct-quebra">{escape(valor)}</code>'


def passos(app: str, urls: dict, alias: str, grupos: list[str], provedor, host: str = "https://<keycloak>") -> list[dict]:
    """O passo a passo, um item por número vermelho das ilustrações (media/entra/az-*.png, make ilustracoes-azure)."""
    lista_grupos = ", ".join(_c(g) for g in grupos) or "os grupos da etapa 2"
    etapa3 = f"/app/sso/?alias={escape(alias)}" if provedor else "/app/sso/?novo=1"
    dados = [
        {"id": "p1", "onde": "Azure", "titulo": "Abrir os Aplicativos empresariais",
         "caminho": "entra.microsoft.com → Identidade → Aplicativos → Aplicativos empresariais → Todos os aplicativos",
         "figuras": [("az-01-aplicativos-empresariais.png", "Lista de aplicativos empresariais")],
         "itens": [("1", "Clique em <b>Novo aplicativo</b>. Não use <em>Registros de aplicativo</em> (App registrations): aquilo é OIDC; o SAML fica aqui.")],
         "nota": "Quem faz precisa ser Administrador de Aplicativos (ou de Aplicativos em Nuvem). Em inglês: Enterprise applications → New application."},
        {"id": "p2", "onde": "Azure", "titulo": "Criar o aplicativo fora da galeria",
         "caminho": "Procurar na Galeria do Microsoft Entra → Criar seu próprio aplicativo",
         "figuras": [("az-02-criar-aplicativo.png", "Criar seu próprio aplicativo")],
         "itens": [("1", f"Nome: {_c(app)}. É o que as pessoas veem no My Apps."),
                   ("2", "Marque <b>Integrar qualquer outro aplicativo que você não encontre na galeria (Não galeria)</b>."),
                   ("3", "<b>Criar</b>. O Azure leva alguns segundos e abre a Visão geral do app.")],
         "nota": "Não procure \"Keycloak\" na galeria: o app da galeria não tem os campos certos para um realm."},
        {"id": "p3", "onde": "Azure", "titulo": "Escolher SAML como método de logon único",
         "caminho": "o app → Logon único",
         "figuras": [("az-03-metodo-saml.png", "Selecionar um método de logon único")],
         "itens": [("1", "No menu do app, <b>Logon único</b>."), ("2", "Clique no cartão <b>SAML</b>.")],
         "nota": ""},
        {"id": "p4", "onde": "Azure", "titulo": "Conhecer a página do SAML",
         "caminho": "o app → Logon único (depois de escolher SAML)",
         "figuras": [("az-04-saml-visao-geral.png", "Logon único baseado em SAML, já configurado")],
         "itens": [("1", "<b>Configuração Básica de SAML</b>: Identificador, URL de Resposta e URL de Logon, todos do Keycloak (passo 5)."),
                   ("2", "<b>Atributos e Declarações</b>: givenname, surname, emailaddress, name, Identificador Exclusivo do Usuário e groups (passos 6 e 7)."),
                   ("3", "<b>Certificados SAML</b>: status, impressão digital, expiração, e-mail de notificação e a URL de metadados que o Keycloak lê (passos 8 e 12). "
                         "<em>Certificados de verificação (opcional)</em> fica como vem: Obrigatório Não, Ativo 0."),
                   ("4", f"<b>Configurar {escape(app)}</b>: URL de Logon, Identificador do Microsoft Entra e URL de logoff do Azure. Não precisa copiar: vêm na metadata."),
                   ("5", f"<b>Test o logon único com {escape(app)}</b>: só funciona depois do passo 12 (passo 13).")],
         "nota": "A figura mostra a página já preenchida, como fica no fim. Os números azuis são do próprio portal."},
        {"id": "p5", "onde": "Azure", "titulo": "Configuração Básica do SAML",
         "caminho": "Logon único → 1 Configuração Básica do SAML → Editar",
         "figuras": [("az-05-configuracao-basica.png", "Configuração Básica do SAML")],
         "itens": [("1", f"<b>Identificador (ID da Entidade)</b>: <b>Adicionar identificador</b>, cole {_c(urls['entity_id'])} e marque <b>Padrão</b>."),
                   ("2", f"<b>URL de Resposta</b>: <b>Adicionar URL de resposta</b>, cole {_c(urls['acs'])} e marque <b>Padrão</b>. Índice em branco."),
                   ("3", f"<b>URL de Logon</b>: {_c(host)}. É para onde o My Apps leva quem clica no ícone do app; "
                         "o Keycloak não aceita login começado pelo Azure, então ele precisa começar no Keycloak (ou no endereço do app). "
                         "Estado de Retransmissão: em branco."),
                   ("4", f"<b>URL de Logoff</b> (opcional): pode ficar em branco. Preenchida com {_c(urls['logout'])}, sair do Azure também encerra a sessão no Keycloak."),
                   ("5", "<b>Salvar</b> e feche o painel. Se perguntar se quer testar, responda <em>Não, testarei mais tarde</em>.")],
         "nota": "Copie exatamente, sem barra no fim. Uma letra diferente dá AADSTS700016 (Identificador) ou AADSTS50011 (URL de Resposta). "
                 "O alias faz parte da URL de Resposta: ele precisa ser o mesmo da etapa 3."},
        {"id": "p6", "onde": "Azure", "titulo": "Atributos e Declarações",
         "caminho": "Logon único → 2 Atributos e Declarações → Editar",
         "figuras": [("az-06-atributos-declaracoes.png", "Atributos e Declarações")],
         "itens": [("1", "<b>Adicionar uma declaração de grupo</b> (próximo passo)."),
                   ("2", "As declarações padrão ficam como estão: <code>givenname</code>, <code>surname</code>, <code>emailaddress</code>, "
                         "<code>name</code> e o <b>Identificador Exclusivo do Usuário</b> (tabela abaixo). O Keycloak lê emailaddress, givenname e surname. Não renomeie."),
                   ("3", "Depois do passo 7 aparece a linha <code>groups</code> = <code>user.groups</code> "
                         "(no detalhe da declaração: <code>user.groups [ApplicationGroup]</code>).")],
         "nota": "Convidados (B2B) às vezes não têm o campo Email: se o login chegar sem e-mail, troque o valor de emailaddress para user.userprincipalname."},
        {"id": "p7", "onde": "Azure", "titulo": "Declaração de grupo",
         "caminho": "Atributos e Declarações → Adicionar uma declaração de grupo",
         "figuras": [("az-07-declaracao-grupo.png", "Declarações de Grupo"), ("az-08-atributo-origem.png", "Opções do Atributo de origem")],
         "itens": [("1", "<b>Grupos atribuídos ao aplicativo</b>. Nunca <em>Todos os grupos</em>: manda TI, Todos etc. e passa do limite de 150 grupos."),
                   ("2", "<b>Atributo de origem</b>: <b>Nomes de exibição de grupo somente nuvem</b> quando os grupos são criados no Azure (segunda figura, item 3). "
                         "Grupos sincronizados do AD local: <em>sAMAccountName</em> (item 2). <em>ID do Grupo</em> (item 1) manda o GUID."),
                   ("3", "<b>Personalizar o nome da declaração de grupo</b>: Nome <code>groups</code>, Namespace vazio."),
                   ("4", "<b>Emitir grupos como declarações de função</b>: desmarcado. Quem transforma grupo em role é o Keycloak."),
                   ("5", "<b>Salvar</b>.")],
         "nota": "Sem o item 3, o claim chega como http://schemas.microsoft.com/ws/2008/06/identity/claims/groups e a chave da etapa 4 precisa ser essa."},
        {"id": "p8", "onde": "Azure", "titulo": "Assinatura e aviso de vencimento",
         "caminho": "Logon único → 3 Certificados SAML → Editar",
         "figuras": [("az-10-opcao-assinatura.png", "Certificado de Autenticação SAML")],
         "itens": [("1", "<b>Opção de Assinatura</b>: <b>Assinar resposta e declaração SAML</b>. O Keycloak exige a declaração assinada."),
                   ("2", "<b>Algoritmo de Assinatura</b>: <b>SHA-256</b>."),
                   ("3", "<b>Email de Notificação</b>: uma caixa do time (não de uma pessoa). O Azure avisa antes de o certificado vencer (3 anos)."),
                   ("4", "<b>Salvar</b>.")],
         "nota": "Quando o certificado for renovado, aplique a etapa 3 de novo com a mesma URL: o Keycloak 21 não relê a metadata sozinho."},
        {"id": "p9", "onde": "Azure", "titulo": "Um grupo de segurança por grupo do Keycloak",
         "caminho": "Microsoft Entra ID → Grupos → Todos os grupos → Novo grupo",
         "figuras": [("az-11-novo-grupo.png", "Novo Grupo")],
         "itens": [("1", "<b>Tipo de grupo</b>: <b>Segurança</b> (não Microsoft 365)."),
                   ("2", f"<b>Nome do grupo</b>: idêntico ao grupo do Keycloak. Neste realm: {lista_grupos}."),
                   ("3", "<b>Tipo de associação</b>: <b>Atribuído</b>, ou <em>Usuário Dinâmico</em> com uma regra (ex.: departamento)."),
                   ("4", "<b>Proprietários</b>: quem aprova as entradas no grupo."),
                   ("5", "<b>Membros</b>: quem terá o acesso."),
                   ("6", "<b>Criar</b>. Repita para cada grupo.")],
         "nota": "Entrar e sair desses grupos no Azure passa a ser o único jeito de dar e tirar acesso: no próximo login o Keycloak acompanha (Sync mode Force)."},
        {"id": "p10", "onde": "Azure", "titulo": "Atribuir os grupos ao aplicativo",
         "caminho": "o app → Usuários e grupos",
         "figuras": [("az-12-usuarios-grupos.png", "Usuários e grupos")],
         "itens": [("1", "<b>Adicionar usuário/grupo</b> → Usuários e grupos → selecione os grupos do passo 9 → função <b>Usuário</b> → <b>Atribuir</b>."),
                   ("2", "A lista deve ter só esses grupos, um por linha.")],
         "nota": "Atribuir grupos exige licença Microsoft Entra ID P1 ou P2. Sem ela, só dá para atribuir usuário por usuário."},
        {"id": "p11", "onde": "Azure", "titulo": "Propriedades: exigir atribuição",
         "caminho": "o app → Propriedades",
         "figuras": [("az-13-propriedades.png", "Propriedades do aplicativo")],
         "itens": [("1", "<b>ID do Aplicativo</b>: anote. A tela <a href=\"/app/azure/\">Azure AD dos realms</a> usa esse ID para validar a assinatura."),
                   ("2", "<b>Atribuição necessária?</b> <b>Sim</b>. Sem isso, qualquer pessoa do tenant entra no Keycloak."),
                   ("3", "<b>Visível para os usuários?</b> Sim para aparecer no My Apps; Não para esconder."),
                   ("4", "<b>Salvar</b>.")],
         "nota": "A URL de Resposta desta tela é só a padrão; a lista completa está na Configuração Básica do SAML."},
        {"id": "p12", "onde": "Azure → assistente", "titulo": "Levar a URL de metadados para o Keycloak",
         "caminho": "Logon único → 3 Certificados SAML",
         "figuras": [("az-09-certificados-saml.png", "Certificados SAML")],
         "itens": [("1", "Confira o <b>Email de Notificação</b> (passo 8)."),
                   ("2", f"Copie a <b>URL de Metadados de Federação do Aplicativo</b>. Na <a href=\"{etapa3}\">etapa 3</a>: tipo Microsoft Entra ID, "
                         f"alias {_c(alias)}, cole a URL, NameID Email, simule e aplique."),
                   ("3", "<b>Editar</b> leva ao painel do passo 8.")],
         "nota": f"Depois, na <a href=\"/app/mapeamento/?alias={escape(alias)}\">etapa 4</a>: chave groups e, para cada grupo, o nome que chega (ou o GUID com ID do Grupo)."},
        {"id": "p13", "onde": "Azure + assistente", "titulo": "Testar e investigar",
         "caminho": "Logon único → Test este aplicativo (ou 5 · Test) → Teste de entrada; depois o app → Logs de entrada",
         "figuras": [("az-14-logs-entrada.png", "Logs de entrada do aplicativo")],
         "itens": [("•", "No Azure: <b>Test este aplicativo</b> abre o painel <em>Test o logon único</em>. <b>Teste de entrada</b> testa com o seu usuário, "
                         "que precisa estar num grupo atribuído ao app (passo 10). Se der erro, cole a mensagem em <b>Solucionando erros</b> e use "
                         "<b>Obter diretrizes de resolução</b>. Para testar com outra pessoa, abra o portal numa aba anônima com a conta dela."),
                   ("1", f"Teste numa janela anônima: <a href=\"{escape(urls['entity_id'])}/account\" target=\"_blank\" rel=\"noopener\">{escape(urls['entity_id'])}/account</a> → <em>Entrar com …</em>. "
                         "Se falhar no Azure, abra <b>Logs de entrada</b> do app e filtre pelo aplicativo."),
                   ("2", "Cada tentativa mostra o <b>Código de erro</b>: procure-o na tabela <a href=\"#erros\">Se der errado</a>."),
                   ("3", "O <b>Motivo da falha</b> diz o que acertar (no exemplo, o usuário não está em nenhum grupo atribuído).")],
         "nota": "Se passou no Azure e falhou no Keycloak, procure o usuário em Conferir e veja o Histórico."},
    ]
    for passo in dados:
        passo["itens"] = [(n, mark_safe(t)) for n, t in passo["itens"]]
        passo["nota"] = mark_safe(passo["nota"])
    return dados


def _alias_entra(cliente, realm: str, provedores: list[dict]) -> str:
    """O provedor que já é do Entra (mapper de e-mail com o claim longo), senão o primeiro, senão "entra"."""
    for p in provedores:
        email = servico.mappers(cliente, realm, p["alias"]).get("email", {}).get("config", {}).get("attribute.name", "")
        if email.startswith(servico.CLAIMS_ENTRA):
            return p["alias"]
    return provedores[0]["alias"] if provedores else "entra"


@com_realm(exige_realm=False)
def view(context, request, realm) -> dict[str, Any]:
    grupos: list[str] = []
    provedor = None
    mapeados = {}
    alias = (request.GET.get("alias") or "").strip()
    if realm:
        cliente = api()
        provedores = servico.listar_provedores(cliente, realm)
        alias = alias or _alias_entra(cliente, realm, provedores)
        provedor = next((p for p in provedores if p["alias"] == alias), None)
        grupos = list(ler_grupos(cliente, realm))
        if provedor:
            mapeados = servico.ler_mapeamento(cliente, realm, alias)
    alias = alias or "entra"
    app = (request.GET.get("app") or "").strip() or f"{realm or 'cliente'} Keycloak"
    urls = servico.urls_sp(url_publica(), realm or "<realm>", alias)
    context.update(
        {
            "alias": alias,
            "app": app,
            "host": url_publica() or "https://<keycloak>",
            "urls": urls,
            "grupos": grupos,
            "provedor": provedor,
            "mapeados": mapeados,
            "claims": CLAIMS,
            "passos": passos(app, urls, alias, grupos, provedor, url_publica() or "https://<keycloak>"),
            "erros": ERROS,
            "chave_longa": servico.CHAVE_GRUPOS_ENTRA_LONGA,
            "checklist": [
                ("Enterprise application criado com SAML", None),
                ("Identificador e URL de Resposta iguais aos do passo 5; URL de Logon no Keycloak", None),
                ("Claim de grupos: Groups assigned to the application, nome groups", None),
                ("Um grupo de segurança por grupo do Keycloak, com o mesmo nome", None),
                ("Grupos atribuídos ao app e Assignment required = Yes", None),
                ("Provedor cadastrado no Keycloak (etapa 3)", bool(provedor)),
                ("Grupos mapeados (etapa 4)", bool(provedor) and bool(grupos) and all(g in mapeados for g in grupos)),
            ],
        }
    )
    return {"request": request, "context": context}
