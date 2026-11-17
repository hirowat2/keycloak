"""Manual de uso: o assistente por tarefa (casos de uso), com fluxo, passo a passo, prints, exemplos e problemas comuns.

A Metodologia explica como cada tela funciona por dentro; este manual diz o que fazer em cada situação do dia a dia.
Os prints são os mesmos da Metodologia (media/metodologia, gerados por make prints).
"""
import os
from typing import Any

from django.conf import settings

# Perfis de quem usa o assistente
PERFIS = [
    ("Admin", "Tem a role ADMIN no realm do login. Simula e aplica tudo, restaura dumps, troca senhas no banco."),
    ("Limited", "Entra no assistente sem a role ADMIN. Vê todas as telas e simula, mas não grava nada."),
]

# Cada caso: id, título, quando usar, quem, pré-requisitos, fluxo (Mermaid), passos (texto, tela, print),
# exemplo (pares rótulo/valor), resultado esperado e erros comuns (sintoma, o que fazer).
CASOS = [
    {
        "id": "cliente-novo",
        "titulo": "Configurar um cliente novo com o SSO dele",
        "quando": "Uma empresa vai usar os apps (Atlas, Linode, Migrator) entrando com a conta corporativa (Entra ID, Google ou Okta).",
        "quem": "Admin do Keycloak + time do SSO do cliente",
        "tempo": "30 a 60 min, a maior parte esperando o time do SSO",
        "pre": [
            "Nome curto do cliente para o realm (minúsculas e hífen), ex.: empresa-x",
            "A URL pública de cada app que o cliente vai usar",
            "Um contato do time do SSO do cliente",
            "Os nomes (ou GUIDs) dos grupos de segurança do SSO que darão acesso a cada app",
        ],
        "diagrama": """flowchart TB
    A["1 · Realm e apps<br/>simular → aplicar"] --> B["2 · Grupos e roles<br/>um grupo por app + admins"]
    B --> C["3 · SSO: copiar<br/>Entity ID e ACS URL"]
    C --> D[["Time do SSO<br/>cria a aplicação SAML<br/>e devolve a URL de metadata"]]
    D --> E["3 · SSO: colar a metadata<br/>e aplicar"]
    E --> F["4 · Grupos do SSO<br/>grupo do SSO → grupo do Keycloak"]
    F --> G(["Login de teste<br/>com um usuário do cliente"])
    G --> H["5 · Conferir<br/>checklist + .env dos apps"]
    H --> I["Times dos apps<br/>colam o .env"]""",
        "passos": [
            ("No Painel, clique em <b>+ Novo realm</b>. Na tela 1, digite o nome do realm e um app por linha "
             "(Client ID, nome e URL). Clique em <b>Simular</b>, confira o plano e clique em <b>Aplicar</b>. "
             "O realm novo passa a ser o realm ativo do menu.", "/app/realm/?novo=1", "04-realm-formulario.png"),
            ("Na tela 2, a matriz já vem com um grupo de admins e um grupo por app. <b>Renomeie os grupos para os mesmos "
             "nomes que o SSO vai mandar</b> (facilita a etapa 4) e aplique.", "/app/grupos/", "07-grupos.png"),
            ("Na tela 3, digite o alias (ex.: <code>entra</code>) e copie o <b>Entity ID</b> e a <b>ACS/Reply URL</b> com "
             "os botões Copiar. Mande as duas para o time do SSO junto com o roteiro da própria tela.", "/app/sso/", "08-sso-urls.png"),
            ("O time do SSO cria a aplicação SAML, inclui o claim de grupos, atribui os grupos e devolve a "
             "<b>URL de metadata</b>. O roteiro de cada portal está na tela.", "/app/sso/", "09-sso-roteiro.png"),
            ("Volte à tela 3, escolha o tipo de SSO, cole a URL de metadata e aplique. Marque <b>login direto</b> se o "
             "cliente só entra pelo SSO (pula a tela de usuário e senha do Keycloak).", "/app/sso/", "10-sso-formulario.png"),
            ("Na tela 4, para cada grupo do Keycloak, informe o valor que chega na asserção (nome do grupo no SSO, ou o "
             "GUID no Entra) e o nome do atributo (<code>groups</code>). Aplique.", "/app/mapeamento/", "12-mapeamento.png"),
            ("Peça para alguém do cliente entrar em um app. Depois, na tela 5, procure o usuário: ele deve aparecer com o "
             "grupo e a role do app. Copie o <code>.env</code> de cada app para os times dos apps.", "/app/conferir/?usuario=", "14-conferir-usuario.png"),
        ],
        "exemplo": [
            ("Realm", "empresa-x"),
            ("App", "atlas-insights · Atlas Insights · https://atlas.empresa-x.com.br"),
            ("Grupos", "empresa-x-admins (ADMIN + todas as roles), empresa-x-atlas-insights (atlas-insights)"),
            ("SSO", "Entra ID, alias entra, metadata https://login.microsoftonline.com/…/federationmetadata.xml?appid=…"),
            ("Mapeamento", "grupo empresa-x-atlas-insights ← groups = 7f3c…-GUID-do-grupo-SG-Atlas"),
        ],
        "resultado": "O usuário do cliente entra no app com a conta corporativa e o app libera o acesso pela role "
                     "atlas-insights. O Conferir mostra o checklist todo verde.",
        "erros": [
            ("O app diz acesso negado", "O mapper do grupo não casou: o Entra manda o GUID do grupo, não o nome. Veja o valor que chegou na tela 5 (vínculo com o SSO) e corrija na tela 4."),
            ("Invalid redirect uri", "A URL do app na etapa 1 está diferente da URL real (http × https, barra no fim, porta). Corrija e aplique de novo."),
            ("Invalid signature no login", "O certificado do SSO mudou. Aplique a etapa 3 de novo com a mesma URL de metadata: ela relê o certificado."),
        ],
    },
    {
        "id": "app-novo",
        "titulo": "Adicionar um app a um cliente que já existe",
        "quando": "Um cliente que já usa o Atlas vai começar a usar o Mongo Migrator.",
        "quem": "Admin do Keycloak",
        "tempo": "5 min",
        "pre": ["O realm do cliente escolhido no menu lateral", "A URL pública do app novo"],
        "diagrama": """flowchart LR
    A["1 · Realm e apps<br/>nova linha"] --> B["2 · Grupos<br/>marcar a role nova"] --> C["4 · Grupos do SSO<br/>mapper do grupo novo"] --> D["5 · Conferir<br/>.env do app"]""",
        "passos": [
            ("Escolha o realm do cliente no menu lateral. Na tela 1, a última linha vem vazia: preencha o app novo. "
             "Simule (os apps antigos aparecem como Sem mudança) e aplique.", "/app/realm/", "06-realm-aplicado.png"),
            ("Na tela 2, crie o grupo do app (ou marque a role nova no grupo que já existe) e aplique.", "/app/grupos/", "07-grupos.png"),
            ("Se o acesso vem de um grupo novo do SSO, peça ao time do SSO para atribuí-lo à aplicação SAML e crie o "
             "mapper na tela 4.", "/app/mapeamento/", "12-mapeamento.png"),
            ("Na tela 5, copie o <code>.env</code> do app novo.", "/app/conferir/", "14-conferir-usuario.png"),
        ],
        "exemplo": [("App novo", "mongo-migrator · Mongo Migrator · https://migrator.empresa-x.com.br"),
                    ("Grupo", "empresa-x-mongo-migrator → role mongo-migrator")],
        "resultado": "Um client novo e uma role com o mesmo nome; quem está no grupo vê o app.",
        "erros": [("A simulação quer mudar os outros apps", "A URL deles no formulário está diferente da cadastrada. Se não era para mudar, corrija o formulário antes de aplicar.")],
    },
    {
        "id": "acesso",
        "titulo": "Dar ou tirar o acesso de uma pessoa",
        "quando": "Alguém entrou ou saiu do time que usa um app.",
        "quem": "Dono do grupo no SSO do cliente (não precisa do assistente)",
        "tempo": "imediato, vale no próximo login",
        "pre": ["O realm já configurado com SSO e mapeamento (caso 1)"],
        "diagrama": """flowchart LR
    S["Dono do grupo põe/tira<br/>a pessoa no SSO"] --> L["Próximo login<br/>da pessoa"]
    L --> M{"Sync mode Force"}
    M -- "está no grupo" --> G["entra no grupo<br/>do Keycloak → role"]
    M -- "saiu do grupo" --> R["sai do grupo<br/>do Keycloak → sem role"]""",
        "passos": [
            ("Peça ao dono do grupo no SSO para incluir ou remover a pessoa do grupo de segurança. <b>Não mexa nos grupos "
             "pelo console do Keycloak</b>: o próximo login desfaz, porque o SSO manda.", "", ""),
            ("Para conferir, a pessoa faz login de novo (ou espera a sessão expirar). Na tela 5, procure o usuário e veja "
             "os grupos e as roles efetivas.", "/app/conferir/?usuario=", "14-conferir-usuario.png"),
        ],
        "exemplo": [("Pessoa", "maria.souza@empresa-x.com.br"), ("Grupo no SSO", "SG-Atlas → empresa-x-atlas-insights → role atlas-insights")],
        "resultado": "No próximo login a role aparece (ou some) no token, e o app libera (ou bloqueia).",
        "erros": [("A pessoa saiu do grupo e ainda entra", "A sessão dela ainda está aberta. Encerre as sessões do usuário no console do Keycloak (Users → Sessions → Sign out) para valer na hora.")],
    },
    {
        "id": "nao-entra",
        "titulo": "Descobrir por que alguém não consegue entrar",
        "quando": "Um usuário reclama de erro no login ou de acesso negado num app.",
        "quem": "Admin ou Limited (só consulta)",
        "tempo": "5 min",
        "pre": ["O usuário ou o e-mail da pessoa", "O realm do cliente no menu lateral"],
        "diagrama": """flowchart TB
    A{"Onde falha?"} -- "tela do Keycloak" --> B{"Mensagem"}
    A -- "dentro do app" --> C["5 · Conferir: roles efetivas<br/>tem a role do app?"]
    B -- "usuário ou senha inválida" --> D["usuário local: senha errada<br/>ou bloqueio por força bruta"]
    B -- "Account is not fully set up" --> E["Migração · usuários incompletos<br/>preencher e-mail e nome"]
    B -- "Invalid redirect uri" --> F["1 · Realm e apps:<br/>URL do app"]
    C -- não --> G["4 · Grupos do SSO:<br/>valor do mapper × o que chegou"]
    C -- sim --> H["app: KEYCLOAK_REQUIRED_ROLE<br/>e KEYCLOAK_REALM no .env"]""",
        "passos": [
            ("Na tela 5, procure o usuário. Veja se ele existe, de qual SSO veio, em quais grupos está e quais roles "
             "efetivas recebe.", "/app/conferir/?usuario=", "14-conferir-usuario.png"),
            ("Sem a role do app: compare o valor dos mappers da tela 4 com o grupo que o SSO manda. No Entra, costuma "
             "chegar o GUID do grupo.", "/app/mapeamento/", "12-mapeamento.png"),
            ("<code>Account is not fully set up</code>: o usuário não tem e-mail, nome ou sobrenome. Liste os incompletos "
             "em Migração da VM, passo 4, e complete pelo console.", "/app/migracao/?incompletos=1", "17-migracao-incompletos.png"),
            ("O checklist da tela 5 aponta configurações fora do guia (ex.: força bruta desligada, client sem PKCE).",
             "/app/conferir/", "13-conferir.png"),
        ],
        "exemplo": [("Sintoma", "maria.souza entra, mas o Atlas diz acesso negado"),
                    ("Achado", "roles efetivas sem atlas-insights; o SSO manda groups = 7f3c…; o mapper espera SG-Atlas"),
                    ("Correção", "tela 4: valor do grupo empresa-x-atlas-insights = 7f3c…")],
        "resultado": "A causa aparece em uma das três telas, sem abrir o console do Keycloak.",
        "erros": [("Usuário local bloqueado", "Depois de várias senhas erradas, o bloqueio temporário por força bruta libera sozinho em alguns minutos.")],
    },
    {
        "id": "migrar-producao",
        "titulo": "Migrar o Keycloak de uma VM para a produção (Kubernetes + Akamai)",
        "quando": "O Keycloak antigo roda em container numa VM e vai para o LKE, com o banco no Akamai Managed PostgreSQL.",
        "quem": "Admin, com acesso SSH à VM, kubectl no cluster e o IP liberado na Akamai",
        "tempo": "30 min + o tempo do restore (minutos para um banco de dezenas de MB)",
        "pre": [
            "Versão do Keycloak da VM igual ou mais antiga que a da produção (o Keycloak não volta versão)",
            "Host primário do cluster de banco (Cloud Manager → Databases → Connection Details)",
            "O IP da sua máquina em Manage Access",
            "kubectl apontando para o cluster de produção",
        ],
        "diagrama": """flowchart TB
    V["Migração da VM: destino<br/>Kubernetes + Akamai"] --> S["Na VM: exportar_vm.sh"]
    S --> P{"Banco da VM"}
    P -- Postgres --> B["keycloak.dump"]
    P -- "H2 / outro" --> A["kc-export.tgz"]
    B --> T["make akamai-testar"] --> R["make akamai-restaurar-dump<br/>keycloak_new → confere → troca"]
    B -. "sem terminal" .-> W["Banco do Keycloak<br/>upload do dump"]
    A --> I["make k8s-importar-realms"]
    R & W & I --> H["Migração: host novo<br/>+ usuários incompletos"]
    H --> X(["Validar e desligar a VM"])""",
        "passos": [
            ("Em Migração da VM, preencha o acesso SSH, o container, o destino <b>Kubernetes + Akamai</b>, o host primário "
             "do cluster e o namespace. A tela monta os comandos.", "/app/migracao/", "20-migracao-akamai.png"),
            ("Rode os comandos do passo 1 na sua máquina: o script vai para a VM, descobre o banco e gera o arquivo.",
             "/app/migracao/", "15-migracao-comandos.png"),
            ("Saiu <code>keycloak.dump</code>: rode <code>make akamai-testar</code> (conexão e se o host é o primário) e "
             "<code>make akamai-restaurar-dump</code>. Ele restaura em <code>keycloak_new</code>, mostra os realms, pede "
             "para digitar <code>keycloak</code>, para o Keycloak, guarda o banco atual como cópia e sobe de novo.", "", ""),
            ("Sem terminal: envie o mesmo <code>keycloak.dump</code> em Banco do Keycloak (caso 6).", "/app/banco/", "23-banco-conferir.png"),
            ("Se o host mudou, faça o passo 3 da Migração em cada realm: apaga a Frontend URL herdada e troca o host nas "
             "URLs dos clients.", "/app/migracao/", "16-migracao-host.png"),
            ("Liste os usuários incompletos (passo 4) e complete pelo console antes de liberar o acesso.",
             "/app/migracao/?incompletos=1", "17-migracao-incompletos.png"),
        ],
        "exemplo": [
            ("VM", "root@vm-antiga, container keycloak (Keycloak 21.1.2 + Postgres)"),
            ("Produção", "LKE, namespace default, imagem quay.io/keycloak/keycloak:21.1"),
            ("Banco", "meu-cluster-default.g2a.akamaidb.net:23159, akmadmin, defaultdb"),
            ("Comando", "make akamai-restaurar-dump AKAMAI_DB_HOST=meu-cluster-default.g2a.akamaidb.net K8S_NS=default"),
        ],
        "resultado": "Os realms da VM no Keycloak da produção, com as mesmas senhas. O banco anterior fica como "
                     "keycloak_antes_<data>, para voltar se precisar.",
        "erros": [
            ("O script recusa: host é uma réplica", "Use o host primário do cluster, não o read-only."),
            ("O dump é mais novo que o Keycloak do deploy", "A VM roda uma versão mais nova que a produção. Atualize a imagem do deploy antes."),
            ("Ainda há conexões com o deploy em 0", "Outro Keycloak (outro ambiente) aponta para o mesmo banco. Descubra quem é antes de confirmar."),
            ("Timeout ao conectar", "O IP não está em Manage Access."),
        ],
    },
    {
        "id": "restaurar",
        "titulo": "Restaurar um dump pelo navegador",
        "quando": "Voltar um backup, trazer o banco de outro ambiente ou refazer uma migração, sem terminal.",
        "quem": "Admin",
        "tempo": "alguns minutos",
        "pre": [
            "O arquivo .dump (pg_dump -Fc) de um Keycloak de versão igual ou mais antiga",
            "A conexão do assistente com o PostgreSQL (do ambiente ou escolhida na tela)",
        ],
        "diagrama": """flowchart LR
    C["1 · Conexão<br/>(ambiente ou outra)"] --> U["2.1 · Enviar o dump"]
    U --> N[("keycloak_new")]
    N --> K{"2.2 · Conferir<br/>migration_model, realms,<br/>versão, admins"}
    K -- "bloqueado" --> D["Desistir:<br/>apaga keycloak_new"]
    K -- "pronto" --> T["2.3 · Digitar o nome<br/>e Trocar"]
    T --> B[("keycloak_antes_AAAAMMDD_HHMMSS<br/>cópia sem conexões")]
    T --> R["Keycloak reinicia<br/>com os dados do dump"]""",
        "passos": [
            ("Para usar outro banco (ex.: o cluster da Akamai), abra <b>Usar outro banco</b>, preencha e clique em "
             "<b>Testar e usar</b>. Nada é salvo se a conexão falhar; a escolha vale só para a sua sessão.", "/app/banco/", "21-banco-conexao.png"),
            ("Confira o banco em uso e escolha o arquivo no passo 2.1. O Keycloak continua no banco atual enquanto o dump "
             "é restaurado no temporário.", "/app/banco/", "22-banco-estado.png"),
            ("No 2.2, confira o <code>migration_model</code>, os realms e os admins do master. Avisos amarelos não "
             "impedem; bloqueios vermelhos sim. Digite o nome do banco e clique em <b>Trocar</b>.", "/app/banco/", "23-banco-conferir.png"),
            ("O banco anterior vira cópia de segurança e a tela mostra o SQL para voltar. No Kubernetes, o assistente "
             "reinicia o Keycloak; no compose, rode o comando que a tela mostra.", "/app/banco/", "24-banco-trocado.png"),
        ],
        "exemplo": [("Arquivo", "keycloak-2026-11-17_0957.dump (gerado no passo 5 da mesma tela)"),
                    ("Conferência", "migration_model pvkxv | 21.1.2 · 21 realms · admins do master: estatcamp, …")],
        "resultado": "O Keycloak volta com os dados do dump. O admin do console passa a ser o do dump.",
        "erros": [
            ("Erros already exists", "Outro Keycloak conectou no temporário e criou tabelas. Veja a seção 3 (quem está conectado) e restaure de novo."),
            ("As outras telas dizem que o Keycloak não respondeu", "O admin que o assistente usa (KEYCLOAK_ADMIN_USER) não existe no dump ou tem outra senha. Troque a senha dele no caso 7 ou ajuste a variável."),
            ("O upload cai no meio", "Arquivo grande demais para o tempo do proxy. Use make akamai-restaurar-dump."),
        ],
    },
    {
        "id": "senha-admin",
        "titulo": "Recuperar o acesso de admin (ninguém sabe a senha)",
        "quando": "Depois de restaurar um dump, ou quando a senha do admin do console se perdeu.",
        "quem": "Admin do assistente",
        "tempo": "2 min",
        "pre": ["O usuário existir no realm master com senha cadastrada"],
        "diagrama": """flowchart LR
    A["Banco do Keycloak<br/>seção 4"] --> B["escolher o admin<br/>do master"] --> C["nova senha<br/>(2 vezes)"] --> D[("hash pbkdf2-sha256<br/>direto no banco")] --> E["reiniciar o Keycloak<br/>(limpa o cache)"]""",
        "passos": [
            ("Na seção 4, escolha o admin, digite a senha nova duas vezes e clique em <b>Trocar a senha</b>. "
             "No Kubernetes o Keycloak reinicia sozinho; no compose, rode o comando indicado.", "/app/banco/#senha", "25-banco-senha-dump.png"),
        ],
        "exemplo": [("Usuário", "estatcamp (master)"), ("Depois", "entrar em https://keycloak…/admin com a senha nova")],
        "resultado": "O admin entra no console com a senha nova. Se for o admin que o assistente usa, ajuste também o KEYCLOAK_ADMIN_PASSWORD dele.",
        "erros": [("Nada mudou: usuário sem senha", "O usuário entra só pelo SSO. Escolha outro admin ou crie um pelo console.")],
    },
    {
        "id": "backup",
        "titulo": "Fazer um backup antes de uma mudança grande",
        "quando": "Antes de atualizar a versão do Keycloak, de uma migração ou de mexer em muitos realms.",
        "quem": "Admin",
        "tempo": "1 min",
        "pre": ["Conexão com o banco (seção 1 da tela Banco do Keycloak)"],
        "diagrama": """flowchart LR
    A["Banco do Keycloak<br/>5 · Gerar e baixar"] --> B["keycloak-AAAA-MM-DD_HHMM.dump<br/>no seu computador"] -. "se der errado" .-> C["2 · Restaurar dump"]""",
        "passos": [
            ("Na seção 5, clique em <b>Gerar e baixar</b>. O Keycloak continua no ar. Guarde o arquivo num lugar seguro: "
             "ele tem os hashes de senha e os segredos dos clients.", "/app/banco/#dump", "25-banco-senha-dump.png"),
        ],
        "exemplo": [("Terminal, mesma coisa", "make akamai-dump AKAMAI_DB_HOST=… (produção) ou pg_dump -Fc (k8s/sql_db.md, seção 5)")],
        "resultado": "Um .dump que volta o Keycloak para este momento pelo caso 6.",
        "erros": [("Não faça commit", "*.dump está no .gitignore: deixe assim.")],
    },
]

# Telas: para que serve e quem pode mexer
TELAS = [
    ("/app/painel/", "Painel", "Realms, andamento das etapas do realm ativo e últimas ações", "todos"),
    ("/app/realm/", "1 · Realm e apps", "Cria o realm e um client OIDC + uma role por app", "Admin aplica"),
    ("/app/grupos/", "2 · Grupos e roles", "Que roles cada grupo dá", "Admin aplica"),
    ("/app/sso/", "3 · SSO corporativo", "URLs para o time do SSO e o provedor SAML", "Admin aplica"),
    ("/app/mapeamento/", "4 · Grupos do SSO", "Grupo do SSO → grupo do Keycloak", "Admin aplica"),
    ("/app/conferir/", "5 · Conferir", "Checklist, usuário, .env dos apps e JSON versionável", "todos"),
    ("/app/migracao/", "Migração da VM", "Comandos da migração (compose, k8s, Akamai), host novo e usuários incompletos", "Admin aplica"),
    ("/app/banco/", "Banco do Keycloak", "Conexão, restaurar dump, conexões, senha de admin e gerar dump", "Admin muda"),
    ("/app/historico/", "Histórico", "Cada simulação e aplicação, com o plano", "todos"),
]

PROBLEMAS = [
    ("A tela diz que o Keycloak não respondeu", "Admin API fora do ar ou credencial errada",
     "Veja se o Keycloak subiu. Depois de restaurar um dump, o admin do assistente (KEYCLOAK_ADMIN_USER/PASSWORD) pode não existir mais: use o caso 7."),
    ("Botão Aplicar não aparece", "Você entrou sem a role ADMIN", "Peça a role ADMIN no realm do login do assistente."),
    ("Simulação mostra mudanças que você não pediu", "O Keycloak foi alterado pelo console", "Confira o plano: aplicar volta ao que o formulário diz."),
    ("Falhou no meio do Aplicar", "Erro do Keycloak num dos passos", "O que já foi feito fica. Corrija e aplique de novo: continua de onde parou."),
    ("Invalid redirect uri", "URL do app diferente da cadastrada", "Etapa 1 (URL do app) ou Migração, passo 3 (host novo)."),
    ("Acesso negado no app", "Sem a role do app no token", "Caso 4: Conferir o usuário e o mapper da etapa 4."),
    ("Account is not fully set up", "Usuário sem e-mail, nome ou sobrenome", "Migração da VM, passo 4."),
    ("already exists no restore", "Banco não estava vazio", "Banco do Keycloak, seção 3: veja quem conecta e restaure de novo."),
    ("migration_model com várias linhas", "Keycloak atualizado (normal) ou banco contaminado", "Normal se as versões sobem; com erros already exists, restaure de novo."),
    ("Timeout no banco da Akamai", "IP fora de Manage Access", "Libere o IP da máquina ou dos nodes do cluster."),
]

GLOSSARIO = [
    ("Realm", "Um espaço isolado do Keycloak, com seus usuários, apps e SSO. Um por cliente."),
    ("Client", "Um app cadastrado no realm. Aqui: público, OIDC, com PKCE S256."),
    ("Role", "Uma permissão que vai no token. Cada app tem uma role com o nome do client; ADMIN vira superuser."),
    ("Grupo", "Junta pessoas e dá roles a elas. O SSO decide quem está em cada grupo."),
    ("SSO / IdP", "O login corporativo do cliente (Entra ID, Google, Okta), ligado ao realm por SAML."),
    ("Metadata", "URL do SSO com certificado e endereços; o Keycloak lê dela a configuração do provedor."),
    ("Mapper", "Regra que copia um dado da asserção SAML para o usuário (e-mail, nome, grupo)."),
    ("Sync mode Force", "A cada login, o Keycloak refaz os dados e grupos do usuário com o que o SSO mandou."),
    ("Plano", "A lista de passos que uma etapa faria. Simular mostra; Aplicar executa."),
    ("Dump", "Cópia do banco do Keycloak (pg_dump -Fc). Restaurar põe tudo de volta, inclusive o master."),
    ("migration_model", "Tabela com as versões do Keycloak por que o banco passou."),
]


def view(context, request) -> dict[str, Any]:
    pasta = os.path.join(settings.MEDIA_ROOT, "metodologia")
    casos = []
    for caso in CASOS:
        passos = [
            {"texto": texto, "tela": tela,
             "imagem": f"metodologia/{imagem}" if imagem and os.path.exists(os.path.join(pasta, imagem)) else ""}
            for texto, tela, imagem in caso["passos"]
        ]
        casos.append({**caso, "passos": passos})
    context.update({"casos": casos, "perfis": PERFIS, "telas": TELAS, "problemas": PROBLEMAS, "glossario": GLOSSARIO})
    return {"request": request, "context": context}
