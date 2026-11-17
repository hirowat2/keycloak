"""Tour explicativo de cada tela (botão "Tour" no topo, ?tour=1 na URL ou o convite da primeira visita).

Cada passo destaca uma parte da tela (``alvo``: seletor CSS; com ``|texto``, o primeiro que contém
esse texto), explica para que serve e pode mostrar uma figura de ``media/`` (os prints da
Metodologia em ``metodologia/`` e as ilustrações do Azure em ``entra/``). Sem alvo, ou se o alvo
não está na tela naquele momento, o passo aparece no centro. ``texto`` aceita HTML simples.

O motor está em ``media/js/tour.js``.
"""

MENU = [
    {"alvo": "#servidor-ativo", "titulo": "Em qual Keycloak",
     "texto": "O seletor <b>Keycloak</b> escolhe o servidor em que todas as telas trabalham. Cadastre outros em "
              "<b>Servidores Keycloak</b>. A escolha vale só para a sua sessão."},
    {"alvo": "#realm-ativo", "titulo": "Em qual realm",
     "texto": "O <b>realm ativo</b> é o cliente em que as etapas mexem. Troque-o antes de trabalhar em outro cliente: "
              "uma ação é recusada se o realm mudou em outra aba."},
]

SIMULAR = {"alvo": "button[value=simular]", "titulo": "Simular primeiro",
           "texto": "<b>Simular</b> nunca grava: mostra o plano com o que seria criado, atualizado ou removido. "
                    "<b>Aplicar</b> grava no Keycloak e pede confirmação (só a role ADMIN vê esse botão).",
           "figura": "metodologia/05-realm-simulacao.png", "legenda": "O plano de uma simulação"}

PLANO = {"alvo": "#plano", "titulo": "O plano",
         "texto": "Cada linha é um passo: <b>Criar</b>, <b>Atualizar</b>, <b>Remover</b> ou <b>Sem mudança</b>. Aplicar de novo é "
                  "seguro: o que já está certo fica como Sem mudança, e se algo falhou no meio, continua de onde parou."}

TOURS = {
    "painel": {"titulo": "Painel", "passos": [
        {"titulo": "Bem-vindo ao assistente",
         "texto": "O assistente aplica no Keycloak, por formulários, o que está nos guias README_sso.md e README_migracao_vm.md. "
                  "Este tour mostra o painel; cada tela tem o seu (botão <b>Tour</b> no topo).",
         "figura": "metodologia/03-painel.png", "legenda": "O painel: (1) realm ativo, (2) menu, (3) novo realm"},
        *MENU,
        {"alvo": ".app-nav", "titulo": "As telas",
         "texto": "<b>Assistente</b>: as 5 etapas para configurar um cliente. <b>Manutenção</b>: servidores, Azure, migração, banco "
                  "e histórico. <b>Ajuda</b>: guia do Azure AD, manual e metodologia."},
        {"alvo": ".ct-card|Etapas do realm", "titulo": "Andamento do realm ativo",
         "texto": "As etapas 1 a 4 do realm ativo, feitas ou não, com um resumo. <b>Fazer</b>/<b>Revisar</b> abre a etapa."},
        {"alvo": ".ct-card|Realms", "titulo": "Todos os realms",
         "texto": "Quantos apps, grupos e provedores SSO cada realm tem. <b>Usar</b> troca o realm ativo."},
        {"alvo": ".ct-card|Últimas ações", "titulo": "Últimas ações",
         "texto": "As 5 últimas simulações e aplicações. O histórico completo, com o plano de cada uma, está em <b>Histórico</b>."},
        {"alvo": ".ct-header .ct-btn--primario", "titulo": "Começar um cliente novo",
         "texto": "<b>+ Novo realm</b> abre a etapa 1 em branco. O passo a passo completo está no Manual, caso 1.",
         "figura": "metodologia/19-painel-final.png", "legenda": "O painel com as 4 etapas feitas"},
    ]},

    "realm": {"titulo": "1 · Realm e apps", "passos": [
        {"titulo": "Etapa 1: o realm e os apps",
         "texto": "Cria (ou acerta) o realm de um cliente com as configurações do guia, a role <code>ADMIN</code> e, para cada app, "
                  "um client OIDC público com PKCE e uma role com o nome do client.",
         "figura": "metodologia/04-realm-formulario.png", "legenda": "Formulário preenchido"},
        {"alvo": "#id_realm", "titulo": "Nome do realm",
         "texto": "Minúsculas e hífen, ex.: <code>empresa-x</code>. Entra nas URLs (<code>/realms/empresa-x</code>) e no "
                  "<code>KEYCLOAK_REALM</code> dos apps. <b>Não muda depois.</b>"},
        {"alvo": "#id_nome_exibicao", "titulo": "Nome na tela de login",
         "texto": "O que aparece no topo da tela de login do Keycloak, ex.: <code>Empresa X</code>."},
        {"alvo": "fieldset|Apps", "titulo": "Um app por linha",
         "texto": "<b>Client ID</b> (o <code>KEYCLOAK_CLIENT_ID</code> do app), nome e <b>URL pública</b>. O callback padrão serve "
                  "aos apps Django. Para mais apps, aplique: a tela ganha outra linha vazia."},
        SIMULAR,
        PLANO,
        {"alvo": "details.ct-card", "titulo": "O que é acertado no realm",
         "texto": "SSL, cadastro e senha desligados (vêm do SSO), login por e-mail, pt-BR, proteção contra força bruta e clients com PKCE.",
         "figura": "metodologia/06-realm-aplicado.png", "legenda": "Aplicado: o realm novo vira o realm ativo"},
    ]},

    "grupos": {"titulo": "2 · Grupos e roles", "passos": [
        {"titulo": "Etapa 2: o que cada grupo pode",
         "texto": "No SSO a empresa controla <b>quem</b> está em cada grupo; aqui você define <b>o que</b> cada grupo dá. "
                  "Os apps leem as roles do token: <code>ADMIN</code> vira superuser e a role com o nome do client libera o app.",
         "figura": "metodologia/07-grupos.png", "legenda": "Matriz grupo × role"},
        {"alvo": "a[href='?sugestao=1']", "titulo": "Estrutura sugerida",
         "texto": "Preenche um grupo de admins (todas as roles) e um grupo por app. Depois ajuste os nomes."},
        {"alvo": "form.ct-card table", "titulo": "A matriz",
         "texto": "Uma linha por grupo, uma coluna por role. Marque o que cada grupo ganha. <b>Use os mesmos nomes dos grupos do SSO</b>: "
                  "a etapa 4 fica direta. Desmarcar tira a role; grupo apagado da lista continua no Keycloak."},
        SIMULAR,
    ]},

    "sso": {"titulo": "3 · SSO corporativo", "passos": [
        {"titulo": "Etapa 3: o login corporativo",
         "texto": "Liga o realm ao SSO da empresa (Entra ID, Google, Okta) por SAML. Uma parte é feita pelo time do SSO, "
                  "no portal deles; esta tela diz exatamente o que pedir."},
        {"alvo": "#id_alias", "titulo": "Alias primeiro",
         "texto": "O alias (ex.: <code>entra</code>) entra nas URLs do SSO e <b>não muda depois</b>. As URLs acima acompanham o que você digita."},
        {"alvo": "#url-entity", "titulo": "Entity ID",
         "texto": "No Azure: <b>Identificador (ID da Entidade)</b>. Use o botão Copiar.",
         "figura": "metodologia/08-sso-urls.png", "legenda": "As URLs que vão para o time do SSO"},
        {"alvo": "#url-acs", "titulo": "ACS / Reply URL",
         "texto": "No Azure: <b>URL de Resposta</b>. É para onde o SSO manda o usuário de volta com a asserção.",
         "figura": "entra/az-05-configuracao-basica.png", "legenda": "Onde essas URLs entram no Azure"},
        {"alvo": ".ct-card|2 · No SSO", "titulo": "Roteiro para o time do SSO",
         "texto": "O passo a passo de cada portal. Para o Azure há um guia completo, com figuras, em <b>Guia do Azure AD</b>.",
         "figura": "metodologia/09-sso-roteiro.png", "legenda": "Roteiro do Entra ID"},
        {"alvo": "#id_metadata_url", "titulo": "URL de metadata",
         "texto": "O time do SSO devolve uma URL de metadata (no Azure: <b>URL de Metadados de Federação do Aplicativo</b>). "
                  "Cole aqui: o Keycloak lê o certificado e os endereços dela.",
         "figura": "entra/az-09-certificados-saml.png", "legenda": "Onde fica a URL no Azure (item 2)"},
        {"alvo": "#id_login_direto", "titulo": "Login direto",
         "texto": "Marcado, o usuário vai direto para o SSO, sem a tela de usuário e senha do Keycloak. Use quando o cliente só entra pelo SSO."},
        {**SIMULAR, "figura": "metodologia/11-sso-aplicado.png", "legenda": "Provedor e mappers criados"},
    ]},

    "mapeamento": {"titulo": "4 · Grupos do SSO", "passos": [
        {"titulo": "Etapa 4: grupo do SSO → grupo do Keycloak",
         "texto": "O Keycloak só sabe dos grupos que o SSO manda na asserção. Cada linha marcada cria um mapper com Sync mode "
                  "<code>Force</code>: quem sai do grupo no SSO sai do grupo aqui no próximo login.",
         "figura": "metodologia/12-mapeamento.png", "legenda": "Um mapper por grupo"},
        {"alvo": "form.ct-card table", "titulo": "Valor e atributo",
         "texto": "<b>Valor no SSO</b>: o que chega na asserção (nome do grupo, ou o GUID no Entra com ID do Grupo). "
                  "<b>Atributo</b>: <code>groups</code>. Os dois precisam bater exatamente, maiúsculas inclusive."},
        {"alvo": ".ct-card|Que valor usar", "titulo": "Que valor usar",
         "texto": "A chave e o valor certos para cada SSO.",
         "figura": "entra/az-07-declaracao-grupo.png", "legenda": "No Azure: o claim de grupos que gera esse valor"},
        SIMULAR,
    ]},

    "conferir": {"titulo": "5 · Conferir", "passos": [
        {"titulo": "Etapa 5: conferir contra o guia",
         "texto": "O realm comparado ao guia, item a item, mais a consulta de um usuário e o <code>.env</code> de cada app.",
         "figura": "metodologia/13-conferir.png", "legenda": "Checklist do realm"},
        {"alvo": ".ct-kpis", "titulo": "Resumo", "texto": "Quantos itens estão de acordo com o guia e quantos faltam acertar."},
        {"alvo": "#usuario", "titulo": "Por que alguém não entra",
         "texto": "Procure a pessoa: aparecem os grupos, as roles que vão no token e o vínculo com o SSO.",
         "figura": "metodologia/14-conferir-usuario.png", "legenda": "Um usuário com grupo e role"},
        {"alvo": ".ct-card|.env de cada app", "titulo": ".env de cada app",
         "texto": "As variáveis para o time de cada app colar no <code>.env</code>, com botão Copiar."},
        {"alvo": "a[href='?exportar=1']", "titulo": "JSON para versionar",
         "texto": "Exporta o realm (sem segredos) para guardar no Git como referência."},
    ]},

    "servidores": {"titulo": "Servidores Keycloak", "passos": [
        {"titulo": "Vários Keycloaks",
         "texto": "Cadastre os Keycloaks que o assistente administra (ex.: a produção) e escolha em qual trabalhar no menu lateral. "
                  "O login no assistente continua no Keycloak do ambiente."},
        {"alvo": "#lista", "titulo": "Os cadastrados",
         "texto": "O ativo da sua sessão, a URL e a credencial de cada um. <b>Usar</b> troca, <b>Testar</b> faz login no master "
                  "e mostra a versão e os realms.",
         "figura": "metodologia/27-servidores-lista.png", "legenda": "Lista e seletor do menu"},
        {"alvo": "#id_url", "titulo": "URL pública",
         "texto": "A raiz do Keycloak, a que tem <code>/realms/master</code>, ex.: <code>https://keycloak.actionstat.app</code>. "
                  "Keycloaks antigos usam <code>/auth</code>: o teste avisa."},
        {"alvo": "#id_url_interna", "titulo": "URL interna",
         "texto": "Só se o assistente alcança o Keycloak por outro endereço (ex.: <code>http://keycloak:8080</code> no mesmo cluster)."},
        {"alvo": "[data-campo=autenticacao]", "titulo": "Credencial do master",
         "texto": "Usuário e senha de um admin do master, ou (melhor em produção) um client com service account e a role admin. "
                  "A senha fica cifrada."},
        {"alvo": "button[value=salvar]", "titulo": "Testar e salvar",
         "texto": "Só grava se o login no master funcionar; se falhar, mostra a causa e a opção de salvar mesmo assim.",
         "figura": "metodologia/26-servidores-cadastro.png", "legenda": "Teste ok antes de salvar"},
    ]},

    "azure": {"titulo": "Azure AD dos realms", "passos": [
        {"titulo": "Logins Microsoft que já existem",
         "texto": "Lista todos os provedores SAML dos realms que apontam para o Azure, mostra o que o app do Azure precisa ter com o "
                  "host atual e acerta o lado do Keycloak. Para criar um do zero, use o Guia do Azure AD."},
        {"alvo": "#inventario", "titulo": "Inventário",
         "texto": "Tenant, Entity ID e situação de cada provedor. <b>Assinatura não validada</b> é grave: aceita resposta SAML forjada. "
                  "<b>Entity ID no host antigo</b> aparece depois de migrar de servidor."},
        {"alvo": "#detalhe", "titulo": "O que o app do Azure precisa ter",
         "texto": "Identificador e URL de Resposta com o host atual, para copiar.",
         "figura": "entra/az-05-configuracao-basica.png", "legenda": "Onde ficam no Azure: Logon único → Configuração Básica do SAML"},
        {"alvo": "#comparar", "titulo": "Comparar",
         "texto": "Cole o que está no Azure: a tela diz o que adicionar, o que marcar como Padrão e o que remover depois."},
        {"alvo": "#ordem", "titulo": "Sem derrubar o login",
         "texto": "Primeiro <b>adicione</b> os valores novos no Azure (os antigos continuam), depois aplique aqui, teste e só então remova os antigos."},
        {"alvo": "#id_app_id", "titulo": "ID do Aplicativo",
         "texto": "Com ele o Keycloak baixa o certificado do app e passa a validar a assinatura. Fica em Propriedades do app no Azure.",
         "figura": "entra/az-13-propriedades.png", "legenda": "ID do Aplicativo (item 1)"},
        {"alvo": "#ajuste button[value=simular]", "titulo": "Simular e aplicar",
         "texto": "A simulação já baixa o metadata do Azure: se o ID estiver errado, você descobre antes de gravar."},
    ]},

    "entra": {"titulo": "Guia do Azure AD", "passos": [
        {"titulo": "Guia do Azure AD",
         "texto": "Tudo o que o time do Azure faz no portal, em 13 passos, com os valores do realm ativo já preenchidos.",
         "figura": "entra/az-04-saml-visao-geral.png", "legenda": "Como fica o app SAML no Azure no fim"},
        {"alvo": "form.ct-card|Seus valores", "titulo": "Seus valores",
         "texto": "O alias (o mesmo da etapa 3) e o nome do app no Azure. O guia inteiro se ajusta."},
        {"alvo": ".ct-card|Andamento", "titulo": "Andamento",
         "texto": "O que já está feito no Keycloak (provedor e grupos mapeados). O que é do Azure, confira com o time."},
        {"alvo": "nav[aria-label=Passos]", "titulo": "Os 13 passos",
         "texto": "Cada passo traz o caminho no portal, o que fazer em cada número vermelho e a ilustração com os mesmos números.",
         "figura": "metodologia/28-entra-guia.png", "legenda": "Um passo do guia"},
        {"alvo": "#p5", "titulo": "O passo mais importante",
         "texto": "Identificador e URL de Resposta precisam ser exatamente estes. Uma letra diferente dá AADSTS700016 ou AADSTS50011."},
        {"alvo": "#erros", "titulo": "Se der errado",
         "texto": "O código AADSTS que o Azure mostra e o que fazer. Os Logs de entrada do app no Azure mostram o código de cada tentativa.",
         "figura": "entra/az-14-logs-entrada.png", "legenda": "Logs de entrada no Azure"},
        {"alvo": "#email", "titulo": "Texto para o time do Azure",
         "texto": "O pedido completo, com as URLs e os grupos, pronto para copiar e mandar por e-mail.",
         "figura": "metodologia/29-entra-email.png", "legenda": "Texto pronto"},
    ]},

    "migracao": {"titulo": "Migração da VM", "passos": [
        {"titulo": "Sair da VM antiga",
         "texto": "Gera os comandos para levar o Keycloak da VM para o compose, para o Kubernetes ou para a produção "
                  "(Kubernetes + PostgreSQL da Akamai), e acerta o host novo nos realms."},
        {"alvo": "form.ct-card", "titulo": "Seus dados",
         "texto": "Acesso SSH à VM, container e destino. Os comandos abaixo se ajustam.",
         "figura": "metodologia/15-migracao-comandos.png", "legenda": "Comandos gerados"},
        {"alvo": "#cmd-vm", "titulo": "1 · Na VM", "texto": "Gera o export (realms em JSON) ou o dump do banco, conforme a versão do Keycloak da VM."},
        {"alvo": "#cmd-b", "titulo": "2B · Dump do banco",
         "texto": "Restaura o <code>keycloak.dump</code> no destino. Para a produção (Akamai), os alvos <code>make akamai-*</code>; "
                  "pelo navegador, a tela Banco do Keycloak.",
         "figura": "metodologia/20-migracao-akamai.png", "legenda": "Destino Akamai"},
        {"alvo": ".ct-card|3 · Host novo", "titulo": "3 · Host novo",
         "texto": "Apaga a Frontend URL herdada e troca o host antigo nos clients. Os provedores do Azure se acertam em <b>Azure AD dos realms</b>.",
         "figura": "metodologia/16-migracao-host.png", "legenda": "Simulação da troca de host"},
        {"alvo": ".ct-card|4 · Usuários", "titulo": "4 · Usuários incompletos",
         "texto": "Quem não tem e-mail, nome ou sobrenome cai em \"Account is not fully set up\". A lista mostra quem acertar.",
         "figura": "metodologia/17-migracao-incompletos.png", "legenda": "Usuários incompletos"},
    ]},

    "banco": {"titulo": "Banco do Keycloak", "passos": [
        {"titulo": "O banco, sem terminal",
         "texto": "Conecta direto no PostgreSQL do Keycloak (funciona com o Keycloak fora do ar): restaurar dump, ver conexões, "
                  "trocar a senha de um admin e gerar dump."},
        {"alvo": "#conexao", "titulo": "1 · Conexão",
         "texto": "A do ambiente ou outra (ex.: a Akamai: porta 23159, <code>akmadmin</code>, <code>defaultdb</code>, SSL require). "
                  "Testar e usar só guarda se conectar.",
         "figura": "metodologia/21-banco-conexao.png", "legenda": "Outra conexão"},
        {"alvo": "#restaurar", "titulo": "2 · Restaurar sem perder nada",
         "texto": "O dump vai para um banco temporário (<code>keycloak_new</code>). Nada muda no banco em uso até a troca.",
         "figura": "metodologia/22-banco-estado.png", "legenda": "Estado e upload"},
        {"alvo": "#conferencia", "titulo": "Conferir",
         "texto": "Versão, realms, usuários e admins do dump. Versão mais nova que o Keycloak bloqueia a troca.",
         "figura": "metodologia/23-banco-conferir.png", "legenda": "Conferência do dump"},
        {"alvo": "#troca", "titulo": "Trocar",
         "texto": "Derruba as conexões, guarda o atual como cópia (<code>keycloak_antes_&lt;data&gt;</code>) e põe o dump no lugar. "
                  "Depois reinicie o Keycloak.",
         "figura": "metodologia/24-banco-trocado.png", "legenda": "Depois da troca"},
        {"alvo": "#conexoes", "titulo": "3 · Quem está conectado", "texto": "O diagnóstico do \"already exists\" e de banco que não renomeia."},
        {"alvo": "#senha", "titulo": "4 · Senha de admin",
         "texto": "Grava a senha nova direto no banco, sem saber a atual. Para quando o admin do dump é desconhecido.",
         "figura": "metodologia/25-banco-senha-dump.png", "legenda": "Senha e dump"},
        {"alvo": "#dump", "titulo": "5 · Gerar dump", "texto": "Backup antes de qualquer mudança grande. O Keycloak continua no ar."},
    ]},

    "historico": {"titulo": "Histórico", "passos": [
        {"titulo": "Quem mudou o quê",
         "texto": "O Keycloak não guarda quem mudou o quê pela Admin API; o assistente guarda: cada simulação e aplicação, com o plano.",
         "figura": "metodologia/18-historico.png", "legenda": "Uma aplicação aberta"},
        {"alvo": "form.ct-filters", "titulo": "Filtrar", "texto": "Por realm, ou só o que foi aplicado (sem as simulações)."},
        {"alvo": "section.ct-card table", "titulo": "Cada linha",
         "texto": "Quando, quem, servidor, realm, etapa e resultado. Clique para ver o plano completo e o erro, se houve."},
    ]},

    "manual": {"titulo": "Manual de uso", "passos": [
        {"titulo": "Manual de uso", "texto": "O que fazer em cada situação, passo a passo, com prints e exemplos."},
        {"alvo": "#mapa", "titulo": "Qual caso eu sigo?", "texto": "Comece pelo fluxograma: ele leva da sua necessidade ao caso certo."},
        {"alvo": ".mt-indice", "titulo": "Índice", "texto": "Os casos de uso, as telas, os problemas comuns e o glossário."},
        {"alvo": "#problemas", "titulo": "Problemas comuns", "texto": "Sintoma, causa provável e o que fazer."},
    ]},

    "metodologia": {"titulo": "Metodologia", "passos": [
        {"titulo": "Metodologia", "texto": "Como cada tela funciona por dentro: o que lê, o que grava no Keycloak, o código e os prints."},
        {"alvo": "#visao", "titulo": "Visão geral", "texto": "Como o assistente, o Keycloak, o SSO e os apps se ligam."},
        {"alvo": "#simular", "titulo": "Simular e aplicar", "texto": "O modelo de plano que todas as etapas seguem."},
        {"alvo": "#codigo", "titulo": "O código", "texto": "Onde fica cada parte, para quem vai manter o assistente."},
    ]},
}
