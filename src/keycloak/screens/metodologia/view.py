"""Metodologia: como o assistente funciona, com diagramas (Mermaid), as partes do código e o passo a passo ilustrado."""
import os
from typing import Any

from django.conf import settings

# Uma seção por etapa: o que muda no Keycloak, onde está no código, o fluxo (Mermaid) e os prints.
# Os números em vermelho dos prints correspondem aos (1), (2)… do texto. Os prints são gerados por
# scripts/capturar_prints.cjs (make prints), num realm de demonstração.
ETAPAS = [
    {
        "id": "entrada", "titulo": "Entrada e painel", "tela": "/app/painel/", "guia": "",
        "resumo": "O login é o mesmo dos apps (Keycloak, realm KC_REALM). O painel mostra os realms e o andamento das etapas do realm escolhido no menu.",
        "muda": "Nada: só lê.", "codigo": "system/sso.py · screens/painel/view.py",
        "diagrama": "",
        "passos": [
            ("01-entrada.png", "Entrada", "A página pública do assistente. (1) Entrar leva ao login do Keycloak."),
            ("02-login.png", "Login pelo Keycloak",
             "(1) Usuário ou e-mail, (2) senha, (3) Entrar. Só entram os e-mails liberados no código; quem tem a role ADMIN "
             "aplica mudanças, os demais só consultam e simulam."),
            ("03-painel.png", "Painel",
             "(1) O realm em que as etapas vão mexer; trocar aqui vale para todas as telas. (2) As etapas, na ordem do guia. (3) Novo realm."),
        ],
    },
    {
        "id": "realm", "titulo": "1 · Realm e apps", "tela": "/app/realm/", "guia": "README_sso.md 1.1–1.7 e 3.1",
        "resumo": "Cria o realm (ou acerta um que já existe) com as configurações recomendadas e cadastra os apps.",
        "muda": "Realm (SSL external, sem cadastro nem \"esqueci a senha\", login com e-mail, pt-BR, bloqueio temporário por força bruta), "
                "role ADMIN, um client OIDC público com PKCE S256 por app e uma role de acesso com o nome de cada client.",
        "codigo": "automacao/realm.py → aplicar(), aplicar_realm(), aplicar_app(), garantir_role()",
        "diagrama": """flowchart LR
    F["Formulário<br/>realm + apps"] --> R["Realm<br/>SSL external · pt-BR<br/>força bruta · sem cadastro"]
    R --> A(("ADMIN"))
    F --> C["Client por app<br/>público · PKCE S256<br/>URL/oidc/callback/"]
    C --> RA(("role com o<br/>nome do client"))
    RA -. "KEYCLOAK_REQUIRED_ROLE" .-> APP["App"]""",
        "passos": [
            ("04-realm-formulario.png", "O formulário",
             "(1) Nome do realm (vai nas URLs e no KEYCLOAK_REALM dos apps). (2) Um app por linha: Client ID, nome e URL pública. "
             "(3) Simular mostra o plano sem gravar. (4) Aplicar grava no Keycloak."),
            ("05-realm-simulacao.png", "A simulação",
             "(1) O plano: cada objeto que seria criado. Nada foi gravado ainda. (2) Aplicar pede confirmação e executa o mesmo plano."),
            ("06-realm-aplicado.png", "Aplicado",
             "(1) O resultado; aplicar de novo daria só \"Sem mudança\". (2) O realm novo já fica selecionado no menu. "
             "A tela volta com o estado do Keycloak e uma linha vazia para mais um app."),
        ],
    },
    {
        "id": "grupos", "titulo": "2 · Grupos e roles", "tela": "/app/grupos/", "guia": "README_sso.md 3.2",
        "resumo": "Diz o que cada grupo pode fazer. Quem está em cada grupo é decidido no SSO (etapa 4).",
        "muda": "Grupos do primeiro nível e as roles de realm de cada um (role mappings). Roles desmarcadas saem do grupo; "
                "grupos tirados da lista não são apagados.",
        "codigo": "automacao/grupos.py → aplicar(), estrutura_sugerida(), ler_grupos()",
        "diagrama": """flowchart LR
    G1["grupo<br/>realm-admins"] --> R1(("ADMIN")) & R2(("atlas-insights")) & R3(("mongo-migrator"))
    G2["grupo<br/>realm-atlas-insights"] --> R2
    R1 & R2 & R3 --> T["token<br/>realm_access.roles"]
    T --> APP["App: ADMIN vira superuser;<br/>a role do app libera o acesso"]""",
        "passos": [
            ("07-grupos.png", "Matriz grupo × role",
             "(1) Já vem com a estrutura sugerida: um grupo de admins com todas as roles e um grupo por app. Ajuste os nomes para "
             "ficarem iguais aos grupos do SSO. (2) Completa com a sugestão a qualquer momento. (3) Aplicar cria os grupos e dá as roles."),
        ],
    },
    {
        "id": "sso", "titulo": "3 · SSO corporativo", "tela": "/app/sso/", "guia": "README_sso.md 2.1–2.6",
        "resumo": "Liga o realm ao SSO da empresa por SAML. Tem uma parte fora do assistente: o time do SSO cria a aplicação SAML "
                  "no portal do Entra, do Google ou do Okta com as URLs que esta tela mostra, e devolve a URL de metadata.",
        "muda": "Provedor SAML (Entity ID do Keycloak, NameID, AuthnRequests e Assertions assinados, Validate Signatures, Trust Email, "
                "Sync mode Force), mappers de e-mail, nome, sobrenome e username e, se marcado, o login direto pelo SSO.",
        "codigo": "automacao/saml.py → urls_sp(), importar_metadata(), aplicar_provedor(), _login_direto()",
        "diagrama": """sequenceDiagram
    autonumber
    participant A as Assistente
    participant T as Time do SSO
    participant K as Keycloak
    A->>T: Entity ID e ACS URL (botão Copiar)
    T->>T: aplicação SAML, grupos e claim groups
    T-->>A: URL de metadata
    A->>K: import-config (só lê o metadata)
    A->>K: provedor SAML: assinaturas, Trust Email, Sync Force
    A->>K: mappers email, firstName, lastName e username
    opt Login direto
      A->>K: Identity Provider Redirector aponta para o alias
    end""",
        "passos": [
            ("08-sso-urls.png", "O que mandar para o time do SSO",
             "As URLs acompanham o alias digitado: (1) Entity ID e (2) ACS/Reply URL. (3) Copia para a área de transferência."),
            ("09-sso-roteiro.png", "Roteiro dentro do SSO",
             "(1) O passo a passo no portal do SSO escolhido: aplicação SAML, claims, grupos de segurança, atribuição e a URL de metadata."),
            ("10-sso-formulario.png", "Cadastro no Keycloak",
             "(1) Qual SSO (define os nomes dos atributos dos mappers). (2) Alias. (3) URL de metadata que o time do SSO devolveu. "
             "(4) Opcional: mandar o usuário direto ao SSO, sem a tela do Keycloak."),
            ("11-sso-aplicado.png", "Aplicado", "(1) Provedor SAML e os quatro mappers criados."),
        ],
    },
    {
        "id": "mapeamento", "titulo": "4 · Grupos do SSO", "tela": "/app/mapeamento/", "guia": "README_sso.md 4.4",
        "resumo": "Faz o grupo do SSO virar o grupo do Keycloak a cada login. Com Sync mode Force, quem sai do grupo no SSO sai "
                  "do grupo no Keycloak no login seguinte.",
        "muda": "Um mapper Advanced Attribute to Group por grupo do Keycloak (atributo e valor que chegam na asserção → grupo). "
                "Grupos desmarcados perdem o mapper.",
        "codigo": "automacao/saml.py → aplicar_mapeamento(), ler_mapeamento()",
        "diagrama": """flowchart LR
    S1["asserção SAML<br/>groups = realm-atlas-insights"] --> M{"mapper do grupo<br/>Advanced Attribute to Group<br/>Sync mode Force"}
    S2["asserção SAML<br/>groups = TI"] -. "sem mapper: ignorado" .-> M
    M --> G["grupo do Keycloak<br/>realm-atlas-insights"]
    G --> R(("role<br/>atlas-insights"))""",
        "passos": [
            ("12-mapeamento.png", "Um mapper por grupo",
             "(1) Os grupos da etapa 2. (2) O valor que chega na asserção: o nome do grupo no SSO, ou o GUID se o Entra mandar "
             "Group ID. (3) O nome do atributo: groups, ou o URI longo do Entra sem customização."),
        ],
    },
    {
        "id": "conferir", "titulo": "5 · Conferir", "tela": "/app/conferir/", "guia": "README_sso.md 1.8, 3.3, 4.5 e Versionando",
        "resumo": "Fecha a configuração: compara o realm com o guia, mostra o que um usuário recebe no token e entrega o que os apps precisam.",
        "muda": "Nada: só lê.",
        "codigo": "automacao/conferir.py → auditar(), consultar_usuario(), env_dos_apps(), exportar()",
        "diagrama": """flowchart LR
    K[("Keycloak")] --> C1["Checklist<br/>contra o guia"]
    K --> C2["Usuário: grupos,<br/>roles efetivas e SSO"]
    K --> C3[".env de cada app"]
    K --> C4["JSON versionável<br/>sem usuários, ids, secrets"]
    C4 --> G["realm/*.json<br/>no Git"]""",
        "passos": [
            ("13-conferir.png", "Checklist",
             "(1) Quantos itens estão de acordo com o guia e quantos faltam; abaixo, o checklist por seção, com o número da seção "
             "do README_sso.md. (2) Baixa o JSON para versionar."),
            ("14-conferir-usuario.png", "Um usuário e o .env dos apps",
             "(1) Busca por usuário ou e-mail. (2) Grupos, roles efetivas (as que vão no token) e o vínculo com o SSO. "
             "(3) O trecho do .env de cada app, com KEYCLOAK_REQUIRED_ROLE."),
        ],
    },
    {
        "id": "migracao", "titulo": "Migração da VM", "tela": "/app/migracao/", "guia": "README_migracao_vm.md",
        "resumo": "Traz os realms de um Keycloak em container numa VM. O script da VM e os alvos do make fazem a cópia; a tela termina o serviço.",
        "muda": "Na troca de host: Frontend URL do realm (apagada) e redirect URIs, post logout e web origins dos clients.",
        "codigo": "scripts/exportar_vm.sh · Makefile (importar-realms, restaurar-dump, k8s-*) · automacao/manutencao.py",
        "diagrama": """flowchart TB
    S["scripts/exportar_vm.sh na VM"] --> I{"docker inspect:<br/>KC_DB?"}
    I -- postgres --> B["pg_dump, sem parar nada<br/>keycloak.dump"]
    I -- "H2 ou outro" --> A["kc.sh export<br/>H2: para ~1 min<br/>kc-export.tgz"]
    B --> RB["make restaurar-dump<br/>apaga o banco daqui"]
    A --> RA["make importar-realms<br/>mantém o master daqui"]
    RA & RB --> T["Tela Migração da VM<br/>host novo · usuários incompletos"]
    T --> D["Validar e desligar a VM"]""",
        "passos": [
            ("15-migracao-comandos.png", "Comandos prontos",
             "(1) Acesso à VM, container e destino. (2) Na VM, o script descobre H2 ou Postgres e gera o arquivo. "
             "(3) Caminho A (kc-export.tgz) e (4) caminho B (keycloak.dump)."),
            ("16-migracao-host.png", "Host novo",
             "(1) Simulação da troca do host antigo nas URLs dos clients e da limpeza da Frontend URL. (2) Host antigo. (3) Aplicar, um realm por vez."),
            ("17-migracao-incompletos.png", "Usuários incompletos",
             "(1) Procura no realm ativo. (2) Usuários sem e-mail, nome ou sobrenome, que veriam a tela de completar o cadastro."),
        ],
    },
    {
        "id": "historico", "titulo": "Histórico", "tela": "/app/historico/", "guia": "",
        "resumo": "Toda simulação e aplicação fica registrada, com o plano completo. O Keycloak não guarda quem mudou o quê pela Admin API.",
        "muda": "Nada no Keycloak.", "codigo": "models.Aplicacao · automacao/web.py → executar()",
        "diagrama": "",
        "passos": [
            ("18-historico.png", "Uma aplicação",
             "(1) Quem, quando, em que realm e em que Keycloak. (2) O plano completo."),
            ("19-painel-final.png", "Realm pronto",
             "(1) As quatro etapas concluídas. Daqui em diante, o acesso é dado e tirado nos grupos do SSO."),
        ],
    },
]

# Partes do código, da tela até a Admin API.
CODIGO = [
    ("Telas", [
        ("src/keycloak/screens/<tela>/view.py", "Uma pasta por tela: monta os formulários, chama a etapa e devolve o contexto do template <tela>.html."),
        ("src/keycloak/screens/config/aside.py", "Menu lateral, em seções, com os grupos (Admin, Limited) que veem cada item."),
        ("src/keycloak/templates/", "base.html (menu, tema, botões Copiar e confirmação do Aplicar), plano.html (tabela do plano) e um template por tela."),
    ]),
    ("Núcleo: src/keycloak/automacao/ (sem Django, dá para usar num script)", [
        ("api.py", "Cliente da Admin REST API. Pega o token do admin no realm master (usuário e senha, ou client credentials) e o renova sozinho."),
        ("plano.py", "Plano e Passo: cada etapa compara o estado atual com o desejado e registra criar/atualizar/remover/sem mudança. Na simulação, nada é executado."),
        ("realm.py", "Etapa 1: realm com as configurações do guia, role ADMIN, clients públicos com PKCE e uma role por app."),
        ("grupos.py", "Etapa 2: grupos e role mappings; estrutura sugerida da seção 3.2."),
        ("saml.py", "Etapas 3 e 4: import do metadata, provedor SAML, mappers de atributo, username, login direto e mappers de grupo."),
        ("conferir.py", "Etapa 5: checklist contra o guia, consulta de usuário, .env dos apps e o JSON versionável."),
        ("manutencao.py", "Pós-migração: troca de host nos clients, Frontend URL e usuários incompletos."),
        ("web.py", "Ponte com as telas: realm ativo, permissões, decorador com_realm e executar(), que roda a etapa e grava o Histórico."),
    ]),
    ("Login e projeto", [
        ("src/system/sso.py", "Valida o token do keycloak.js (assinatura, emissor, client, validade), aplica EMAILS_PERMITIDOS e põe quem tem a role ADMIN no grupo Admin."),
        ("src/keycloak/management/commands/preparar_login.py", "Roda no entrypoint: cria o client keycloak-assistente e a role ADMIN no realm do login, se faltarem."),
        ("src/keycloak/models.py", "Aplicacao: o registro do Histórico (etapa, realm, usuário, simulação ou não, plano e erro)."),
    ]),
    ("Infraestrutura", [
        ("docker-compose.yml", "Keycloak + Postgres, assistente + Postgres e o Traefik (só se ninguém publicar a 443)."),
        ("kustomization.yaml + k8s/", "O mesmo no Kubernetes: Keycloak, StatefulSet do banco, assistente com SQLite em PVC e os Ingress."),
        ("scripts/exportar_vm.sh", "Roda na VM antiga: docker inspect, escolhe o caminho A ou B e gera kc-export.tgz ou keycloak.dump."),
        ("Makefile", "compose, test, importar-realms, restaurar-dump, k8s-* e prints (estes prints)."),
        ("tests/", "Unitários e a integração que percorre as telas contra um Keycloak de verdade (KEYCLOAK_TESTE_URL)."),
    ]),
]


def view(context, request) -> dict[str, Any]:
    pasta = os.path.join(settings.MEDIA_ROOT, "metodologia")
    numero, etapas = 0, []
    for etapa in ETAPAS:
        passos = []
        for arquivo, titulo, texto in etapa["passos"]:
            numero += 1
            if os.path.exists(os.path.join(pasta, arquivo)):
                passos.append({"imagem": f"metodologia/{arquivo}", "titulo": titulo, "texto": texto, "numero": numero})
        etapas.append({**etapa, "passos": passos})
    context.update({"etapas": etapas, "codigo": CODIGO, "tem_prints": any(e["passos"] for e in etapas)})
    return {"request": request, "context": context}
