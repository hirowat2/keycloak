// Ilustrações do portal do Azure (Microsoft Entra ID) para o Guia do Azure AD (media/entra/az-*.png).
//
// Não são capturas de tela: são páginas HTML que reproduzem os campos do portal em português (como
// aparecem num tenant pt-BR), com valores fictícios e os números vermelhos citados no guia. O portal
// muda de layout com frequência; os nomes dos campos são estes.
//
//   make ilustracoes-azure     (precisa do playwright-core, como o make prints)
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

function playwright() {
  try {
    return require("playwright-core");
  } catch {
    const cache = path.join(os.homedir(), ".npm", "_npx");
    for (const dir of fs.existsSync(cache) ? fs.readdirSync(cache) : []) {
      const candidato = path.join(cache, dir, "node_modules", "playwright-core");
      if (fs.existsSync(candidato)) return require(candidato);
    }
    throw new Error("playwright-core não encontrado: rode pelo make ilustracoes-azure.");
  }
}

const SAIDA = path.join(__dirname, "..", "media", "entra");
// Valores fictícios, os mesmos do exemplo do guia
const APP = "Empresa X Keycloak";
const HOST = "https://keycloak.exemplo.com.br";
const REALM = "empresa-x";
const ALIAS = "entra";
const ENTITY = `${HOST}/realms/${REALM}`;
const ACS = `${ENTITY}/broker/${ALIAS}/endpoint`;
const TENANT = "1a2b3c4d-0000-4000-8000-00000000abcd";
const APP_ID = "7f3c2a1e-1111-4222-8333-444455556666";
const GRUPOS = [`${REALM}-admins`, `${REALM}-atlas`, `${REALM}-linode`];

const CSS = `
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif; color: #242424; background: #faf9f8; }
.topo { height: 40px; background: #0f6cbd; color: #fff; display: flex; align-items: center; gap: 24px; padding: 0 16px; }
.topo b { font-size: 15px; }
.busca { flex: 0 0 520px; height: 28px; background: #fff; border-radius: 3px; color: #707070; font-size: 13px; padding: 5px 10px; }
.selo { margin-left: auto; background: rgba(255,255,255,.18); border-radius: 10px; padding: 2px 10px; font-size: 12px; }
.trilha { padding: 12px 24px 0; font-size: 13px; color: #0f6cbd; }
.trilha span { color: #424242; }
.cabeca { display: flex; gap: 12px; align-items: center; padding: 8px 24px 14px; border-bottom: 1px solid #e1dfdd; background: #fff; }
.icone { width: 34px; height: 34px; border-radius: 4px; background: linear-gradient(135deg, #2b88d8, #0f6cbd); flex: none; }
.cabeca h1 { margin: 0; font-size: 22px; font-weight: 600; }
.cabeca p { margin: 0; color: #605e5c; font-size: 13px; }
.corpo { display: flex; min-height: 560px; background: #fff; }
.menu { width: 230px; flex: none; border-right: 1px solid #e1dfdd; padding: 8px 0; font-size: 13.5px; }
.menu div { padding: 6px 28px; }
.menu .grupo { padding: 10px 16px 4px; font-weight: 600; }
.menu .ativo { background: #edebe9; border-left: 3px solid #0f6cbd; padding-left: 25px; font-weight: 600; }
.conteudo { flex: 1; padding: 16px 28px 24px; min-width: 0; }
.barra { display: flex; gap: 22px; color: #0f6cbd; font-size: 13.5px; padding: 4px 0 12px; border-bottom: 1px solid #edebe9; margin-bottom: 14px; }
.campo { display: grid; grid-template-columns: 290px 1fr; gap: 16px; align-items: center; margin: 12px 0; }
.campo label { font-weight: 600; font-size: 13.5px; }
.campo label i { color: #a4262c; font-style: normal; }
input, .caixa { width: 100%; height: 32px; border: 1px solid #8a8886; border-radius: 2px; padding: 5px 9px; font: inherit; background: #fff; }
.ro { background: #f3f2f1; border-color: #c8c6c4; font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 12.5px; color: #323130; }
.mono { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 12.5px; }
.chave { display: inline-flex; border: 1px solid #8a8886; border-radius: 2px; overflow: hidden; }
.chave span { padding: 4px 18px; }
.chave .on { background: #0f6cbd; color: #fff; }
.botao { display: inline-block; background: #0f6cbd; color: #fff; padding: 6px 18px; border-radius: 2px; font-weight: 600; }
.botao.sec { background: #fff; color: #242424; border: 1px solid #8a8886; font-weight: 400; }
.link { color: #0f6cbd; }
.painel { position: absolute; top: 40px; right: 0; bottom: 0; width: 640px; background: #fff; box-shadow: -8px 0 24px rgba(0,0,0,.18); padding: 22px 28px; }
.painel h2 { margin: 0 0 4px; font-size: 20px; font-weight: 600; }
.painel .sub { color: #605e5c; font-size: 13px; margin: 0 0 14px; }
.sombra { position: absolute; inset: 40px 640px 0 0; background: rgba(0,0,0,.25); }
.cartao { border: 1px solid #e1dfdd; border-radius: 4px; padding: 14px 16px; margin: 0 0 14px; position: relative; }
.cartao h3 { margin: 0 0 8px; font-size: 15px; display: flex; align-items: center; gap: 10px; }
.cartao h3 .num { width: 22px; height: 22px; border-radius: 50%; background: #0f6cbd; color: #fff; font-size: 12px; display: inline-flex; align-items: center; justify-content: center; }
.cartao .editar { position: absolute; right: 14px; top: 12px; color: #0f6cbd; font-size: 13px; }
.kv { display: grid; grid-template-columns: 300px 1fr; gap: 4px 12px; font-size: 13px; }
.kv div:nth-child(odd) { color: #605e5c; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; font-weight: 600; border-bottom: 1px solid #e1dfdd; padding: 8px; }
td { border-bottom: 1px solid #f3f2f1; padding: 8px; }
.radio { display: flex; align-items: center; gap: 8px; margin: 7px 0; }
.radio b { width: 16px; height: 16px; border: 1px solid #605e5c; border-radius: 50%; display: inline-block; position: relative; }
.radio b.on::after { content: ""; position: absolute; inset: 3px; border-radius: 50%; background: #0f6cbd; }
.check { display: flex; align-items: center; gap: 8px; margin: 7px 0; }
.check b { width: 16px; height: 16px; border: 1px solid #605e5c; border-radius: 2px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; }
.check b.on { background: #0f6cbd; border-color: #0f6cbd; color: #fff; }
.blocos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.bloco { border: 1px solid #e1dfdd; border-radius: 4px; padding: 16px; height: 130px; }
.bloco h4 { margin: 0 0 6px; font-size: 15px; }
.bloco p { margin: 0; color: #605e5c; font-size: 12.5px; }
.lista-op div { padding: 7px 10px; }
.lista-op .on { background: #edebe9; }
.erro { color: #a4262c; font-weight: 600; }
.ok { color: #107c10; font-weight: 600; }
.tag { display: inline-block; background: #eff6fc; color: #0f6cbd; border-radius: 2px; padding: 0 6px; font-size: 12px; }
`;

// Marcadores numerados (como nos prints do assistente): caixa vermelha + número no canto.
const MARCAR = `
document.querySelectorAll("[data-n]").forEach((el) => {
  const r = el.getBoundingClientRect();
  const caixa = document.createElement("div");
  Object.assign(caixa.style, { position: "absolute", left: Math.max(2, r.left - 5) + scrollX + "px", top: r.top - 4 + scrollY + "px",
    width: r.width + 10 - Math.max(0, 2 - (r.left - 5)) + "px", height: r.height + 8 + "px", border: "2.5px solid #e11d48", borderRadius: "5px", zIndex: 9 });
  const num = document.createElement("div");
  num.textContent = el.dataset.n;
  Object.assign(num.style, { position: "absolute", left: Math.max(4, r.left - 18) + scrollX + "px", top: r.top - 17 + scrollY + "px",
    width: "26px", height: "26px", borderRadius: "50%", background: "#e11d48", color: "#fff", font: "700 14px sans-serif",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10, border: "2px solid #fff" });
  document.body.append(caixa, num);
});`;

const topo = () => `<div class="topo"><b>Microsoft Azure</b><div class="busca">Pesquisar recursos, serviços e documentos (G+/)</div><span class="selo">ilustração · portal do Azure</span></div>`;

function pagina({ trilha, titulo, sub, menu = [], ativo, corpo }) {
  const itens = menu.map((m) => (m.startsWith("#") ? `<div class="grupo">${m.slice(1)}</div>` : `<div class="${m === ativo ? "ativo" : ""}" ${m === ativo && ativo.includes("|") ? "" : ""}>${m}</div>`)).join("");
  return `${topo()}<div class="trilha">${trilha}</div>
    <div class="cabeca"><div class="icone"></div><div><h1>${titulo}</h1><p>${sub}</p></div></div>
    <div class="corpo">${menu.length ? `<nav class="menu">${itens}</nav>` : ""}<main class="conteudo">${corpo}</main></div>`;
}

const MENU_APP = ["Visão geral", "Plano de Implantação", "Diagnosticar e resolver problemas", "#Gerenciar", "Propriedades",
  "Proprietários", "Funções e administradores", "Usuários e grupos", "Logon único", "Provisionamento", "Autoatendimento",
  "#Segurança", "Acesso Condicional", "Permissões", "#Atividade", "Logs de entrada", "Logs de auditoria"];
const TRILHA_APP = `Página inicial › Aplicativos empresariais | Todos os aplicativos › <span>${APP}</span>`;
const app = (secao, corpo, extra = {}) => pagina({ trilha: TRILHA_APP, titulo: `${APP} | ${secao}`, sub: "Aplicativo Empresarial", menu: MENU_APP, ativo: secao, corpo, ...extra });

const FIGURAS = {
  // 1 · Enterprise applications → New application
  "az-01-aplicativos-empresariais": { largura: 1300, html: pagina({
    trilha: "Página inicial › Microsoft Entra ID › <span>Aplicativos empresariais</span>",
    titulo: "Aplicativos empresariais | Todos os aplicativos", sub: "Microsoft Entra ID",
    menu: ["Visão geral", "#Gerenciar", "Todos os aplicativos", "Proxy de aplicativo", "Consentimento e permissões", "#Atividade", "Logs de entrada"],
    ativo: "Todos os aplicativos",
    corpo: `<div class="barra"><span data-n="1">＋ Novo aplicativo</span><span>↻ Atualizar</span><span>⤓ Baixar (exportar)</span><span>☰ Colunas</span></div>
      <input class="caixa" value="" placeholder="Pesquisar por nome do aplicativo ou ID do objeto" style="max-width:480px">
      <table style="margin-top:14px"><tr><th>Nome</th><th>ID do objeto</th><th>ID do Aplicativo</th><th>Página inicial</th></tr>
      <tr><td>Microsoft Teams</td><td class="mono">5c2e…</td><td class="mono">cc15fd57…</td><td></td></tr>
      <tr><td>Salesforce</td><td class="mono">91af…</td><td class="mono">a0e2c3d4…</td><td>https://login.salesforce.com</td></tr>
      <tr><td>Zoom</td><td class="mono">0b7d…</td><td class="mono">3c1f0e9a…</td><td>https://zoom.us</td></tr></table>`,
  }) },

  // 2 · Create your own application
  "az-02-criar-aplicativo": { largura: 1300, html: pagina({
    trilha: "Página inicial › Aplicativos empresariais › <span>Procurar na Galeria do Microsoft Entra</span>",
    titulo: "Procurar na Galeria do Microsoft Entra", sub: "",
    corpo: `<div class="barra"><span>＋ Criar seu próprio aplicativo</span><span>Solicitar novo aplicativo da galeria</span></div>
      <p style="color:#605e5c">Aplicativos de nuvem em destaque…</p>`,
  }) + `<div class="sombra"></div><div class="painel">
      <h2>Criar seu próprio aplicativo</h2><p class="sub">Se você estiver desenvolvendo seu próprio aplicativo, usando o Proxy de Aplicativo ou quiser integrar um aplicativo que não está na galeria, crie seu próprio aplicativo aqui.</p>
      <p style="font-weight:600;margin:18px 0 6px">Qual é o nome do seu aplicativo?</p>
      <input data-n="1" value="${APP}">
      <p style="font-weight:600;margin:20px 0 6px">O que você deseja fazer com seu aplicativo?</p>
      <div class="radio"><b></b>Configurar o Proxy de Aplicativo para acesso remoto seguro a um aplicativo local</div>
      <div class="radio"><b></b>Registrar um aplicativo para integração com o Microsoft Entra ID (aplicativo que você está desenvolvendo)</div>
      <div class="radio" data-n="2"><b class="on"></b>Integrar qualquer outro aplicativo que você não encontre na galeria (Não galeria)</div>
      <div style="position:absolute;bottom:24px;left:28px"><span class="botao" data-n="3">Criar</span></div></div>` },

  // 3 · Single sign-on → SAML
  "az-03-metodo-saml": { largura: 1300, html: app("Logon único", `
      <p style="font-weight:600;font-size:16px;margin:0 0 4px">Selecionar um método de logon único</p>
      <p style="color:#605e5c;margin:0 0 16px">Ajuda <span class="link">Saiba mais</span></p>
      <div class="blocos">
        <div class="bloco"><h4>Desabilitado</h4><p>O logon único não está habilitado. O usuário não poderá iniciar o aplicativo pelo My Apps.</p></div>
        <div class="bloco" data-n="2" style="border-color:#0f6cbd"><h4>SAML</h4><p>Proteja facilmente o aplicativo com a autenticação SAML (Security Assertion Markup Language).</p></div>
        <div class="bloco"><h4>Baseado em senha</h4><p>O armazenamento de senhas permite que os usuários façam login com um clique.</p></div>
        <div class="bloco"><h4>Vinculado</h4><p>Vincular a um aplicativo no Portal de Aplicativos do Microsoft Entra.</p></div>
      </div>`, { ativo: "Logon único" }).replace('<div class="ativo" >Logon único</div>', '<div class="ativo" data-n="1">Logon único</div>') },

  // 4 · SAML-based sign-on (visão geral)
  "az-04-saml-visao-geral": { largura: 1300, altura: 980, html: app("Logon único baseado em SAML", `
      <div class="barra"><span>⤒ Carregar arquivo de metadados</span><span>⇄ Alterar o modo de logon único</span><span>✓ Test este aplicativo</span></div>
      <div class="cartao" data-n="1"><h3><span class="num">1</span>Configuração Básica de SAML</h3><span class="editar">✎ Editar</span>
        <div class="kv"><div>Identificador (ID da Entidade)</div><div class="mono">${ENTITY}</div><div>URL de Resposta (URL do Serviço do Consumidor de Declaração)</div><div class="mono">${ACS}</div>
        <div>URL de Logon</div><div class="mono">${HOST}</div><div>Estado de Retransmissão (Opcional)</div><div>Opcional</div><div>URL de Logoff (Opcional)</div><div>Opcional</div></div></div>
      <div class="cartao" data-n="2"><h3><span class="num">2</span>Atributos e Declarações</h3><span class="editar">✎ Editar</span>
        <div class="kv"><div>givenname</div><div>user.givenname</div><div>surname</div><div>user.surname</div><div>emailaddress</div><div>user.mail</div><div>name</div><div>user.userprincipalname</div><div>Identificador Exclusivo do Usuário</div><div>user.userprincipalname</div><div>groups</div><div>user.groups</div></div></div>
      <div class="cartao" data-n="3"><h3><span class="num">3</span>Certificados SAML</h3><span class="editar">✎ Editar</span>
        <div class="kv"><div>Status</div><div>Ativo</div><div>Impressão Digital</div><div class="mono">A1B2C3D4E5F6…</div><div>Expiração</div><div>17/11/2029, 10:12:04</div><div>Email de Notificação</div><div>ti@exemplo.com.br</div>
        <div>URL de Metadados de Federação do Aplicativo</div><div class="mono">https://login.microsoftonline.com/${TENANT.slice(0, 8)}…/federationmetadata/2007-06/federationmetadata.xml?appid=${APP_ID.slice(0, 8)}… ⧉</div>
        <div>Certificados de verificação (opcional)</div><div>Obrigatório Não · Ativo 0 · Expirou 0</div></div></div>
      <div class="cartao" data-n="4"><h3><span class="num">4</span>Configurar ${APP}</h3>
        <div class="kv"><div>URL de logon</div><div class="mono">https://login.microsoftonline.com/${TENANT.slice(0, 8)}…/saml2</div><div>Identificador do Microsoft Entra</div><div class="mono">https://sts.windows.net/${TENANT.slice(0, 8)}…/</div><div>URL de logoff</div><div class="mono">https://login.microsoftonline.com/${TENANT.slice(0, 8)}…/saml2</div></div></div>
      <div class="cartao" data-n="5"><h3><span class="num">5</span>Test o logon único com o ${APP}</h3><span class="botao">Test</span></div>`) },

  // 5 · Basic SAML Configuration (editar)
  "az-05-configuracao-basica": { largura: 1300, altura: 900, html: app("Logon único baseado em SAML", "") + `<div class="sombra"></div><div class="painel">
      <h2>Configuração Básica de SAML</h2><p class="sub"><span class="link">💾 Salvar</span> &nbsp; <span class="link">Tem comentários?</span></p>
      <div data-n="1"><p style="font-weight:600;margin:12px 0 6px">Identificador (ID da Entidade) <i style="color:#a4262c;font-style:normal">*</i></p>
        <table><tr><th></th><th>Padrão</th><th></th></tr><tr><td><input class="mono" value="${ENTITY}"></td><td style="width:60px;text-align:center"><span class="check" style="justify-content:center"><b class="on">✓</b></span></td><td style="width:30px">🗑</td></tr></table>
        <span class="link" style="font-size:13px">Adicionar identificador</span></div>
      <div data-n="2"><p style="font-weight:600;margin:16px 0 6px">URL de Resposta (URL do Serviço do Consumidor de Declaração) <i style="color:#a4262c;font-style:normal">*</i></p>
        <table><tr><th></th><th>Índice</th><th>Padrão</th></tr><tr><td><input class="mono" value="${ACS}"></td><td style="width:60px"><input value="" style="width:44px"></td><td style="width:60px;text-align:center"><span class="check" style="justify-content:center"><b class="on">✓</b></span></td></tr></table>
        <span class="link" style="font-size:13px">Adicionar URL de resposta</span></div>
      <div data-n="3"><p style="font-weight:600;margin:16px 0 6px">URL de Logon (Opcional)</p><input class="mono" value="${HOST}"></div>
      <div><p style="font-weight:600;margin:16px 0 6px">Estado de Retransmissão (Opcional)</p><input placeholder="Insira um estado de retransmissão"></div>
      <div data-n="4"><p style="font-weight:600;margin:16px 0 6px">URL de Logoff (Opcional)</p><input placeholder="Insira uma URL de logoff"></div>
      <div style="margin-top:20px"><span class="botao" data-n="5">💾 Salvar</span></div></div>` },

  // 6 · Attributes & Claims
  "az-06-atributos-declaracoes": { largura: 1300, html: pagina({
    trilha: `Página inicial › ${APP} | Logon único › <span>Logon único baseado em SAML</span>`,
    titulo: "Atributos e Declarações", sub: "",
    corpo: `<div class="barra"><span>＋ Adicionar nova declaração</span><span data-n="1">＋ Adicionar uma declaração de grupo</span><span>☰ Colunas</span></div>
      <p style="font-weight:600;margin:6px 0">Declaração necessária</p>
      <table><tr><th>Nome da declaração</th><th>Tipo</th><th>Valor</th></tr><tr><td>Identificador de Usuário Exclusivo (ID de Nome)</td><td>SAML</td><td>user.userprincipalname [nameid-format:emailAddress]</td></tr></table>
      <p style="font-weight:600;margin:16px 0 6px">Declarações adicionais</p>
      <table data-n="2"><tr><th>Nome da declaração</th><th>Tipo</th><th>Valor</th></tr>
      <tr><td class="mono">http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress</td><td>SAML</td><td>user.mail</td></tr>
      <tr><td class="mono">http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname</td><td>SAML</td><td>user.givenname</td></tr>
      <tr><td class="mono">http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name</td><td>SAML</td><td>user.userprincipalname</td></tr>
      <tr><td class="mono">http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname</td><td>SAML</td><td>user.surname</td></tr></table>
      <table style="margin-top:6px"><tr data-n="3"><td class="mono" style="width:56%">groups</td><td>SAML</td><td>user.groups [ApplicationGroup]</td></tr></table>`,
  }) },

  // 7 · Group Claims
  "az-07-declaracao-grupo": { largura: 1300, altura: 860, html: pagina({ trilha: "", titulo: "Atributos e Declarações", sub: "", corpo: "" }) + `<div class="sombra"></div><div class="painel">
      <h2>Declarações de Grupo</h2><p class="sub">Gerencie as declarações de grupo usadas pelo Microsoft Entra ID para popular os tokens SAML emitidos para seu aplicativo</p>
      <p style="font-weight:600;margin:14px 0 4px">Quais grupos associados ao usuário devem ser retornados na declaração?</p>
      <div class="radio"><b></b>Nenhum</div><div class="radio"><b></b>Todos os grupos</div><div class="radio"><b></b>Grupos de segurança</div><div class="radio"><b></b>Funções de diretório</div>
      <div class="radio" data-n="1"><b class="on"></b>Grupos atribuídos ao aplicativo</div>
      <div class="campo" data-n="2" style="grid-template-columns:150px 1fr"><label>Atributo de origem <i>*</i></label><div class="caixa">Nomes de exibição de grupo somente nuvem ⌄</div></div>
      <p style="font-weight:600;margin:18px 0 4px">Opções avançadas</p>
      <div class="check"><b></b>Filtrar grupos</div>
      <div data-n="3"><div class="check"><b class="on">✓</b>Personalizar o nome da declaração de grupo</div>
        <div class="campo" style="grid-template-columns:150px 1fr;margin-left:24px"><label>Nome <i>*</i></label><input value="groups"></div>
        <div class="campo" style="grid-template-columns:150px 1fr;margin-left:24px"><label>Namespace</label><input value=""></div></div>
      <div class="check" data-n="4"><b></b>Emitir grupos como declarações de função</div>
      <div style="margin-top:18px"><span class="botao" data-n="5">Salvar</span></div></div>` },

  // 8 · Atributo de origem
  "az-08-atributo-origem": { largura: 900, altura: 430, html: `${topo()}<div style="padding:24px 40px;background:#fff;height:390px">
      <div class="campo" style="grid-template-columns:150px 1fr"><label>Atributo de origem <i style="color:#a4262c;font-style:normal">*</i></label><div class="caixa">Nomes de exibição de grupo somente nuvem ⌄</div></div>
      <div class="lista-op" style="margin-left:166px;border:1px solid #c8c6c4;box-shadow:0 4px 12px rgba(0,0,0,.15)">
        <div data-n="1">ID do Grupo</div><div>sAMAccountName</div><div data-n="2">NetbiosDomain\\sAMAccountName</div><div>DNSDomain\\sAMAccountName</div>
        <div>Nome da conta SAM local do aplicativo local</div><div class="on" data-n="3">Nomes de exibição de grupo somente nuvem</div></div></div>` },

  // 9 · Certificados SAML
  "az-09-certificados-saml": { largura: 1300, altura: 760, html: app("Logon único baseado em SAML", `
      <div class="cartao"><h3><span class="num">3</span>Certificados SAML</h3>
        <p style="font-weight:600;margin:4px 0 8px">Certificado de Autenticação de Token</p><span class="editar" data-n="3">✎ Editar</span>
        <div class="kv"><div>Status</div><div class="ok">Ativo</div><div>Impressão Digital</div><div class="mono">A1B2C3D4E5F6…</div>
        <div>Expiração</div><div>17/11/2029, 10:12:04</div></div>
        <div class="kv" data-n="1" style="margin-top:4px"><div>Email de Notificação</div><div>ti@exemplo.com.br</div></div>
        <div class="kv" data-n="2" style="margin-top:8px;align-items:center"><div>URL de Metadados de Federação do Aplicativo</div><div style="display:flex;gap:6px;align-items:center"><input class="ro" value="https://login.microsoftonline.com/${TENANT}/federationmetadata/2007-06/federationmetadata.xml?appid=${APP_ID}"> ⧉</div></div>
        <div class="kv" style="margin-top:8px"><div>Certificado (Base64)</div><div class="link">Baixar</div><div>Certificado (Bruto)</div><div class="link">Baixar</div><div>XML de Metadados de Federação</div><div class="link">Baixar</div></div>
        <p style="font-weight:600;margin:16px 0 4px">Certificados de Verificação (opcional)</p><div class="kv"><div>Obrigatório</div><div>Não</div><div>Ativo</div><div>0</div></div></div>`) },

  // 10 · Opção de assinatura
  "az-10-opcao-assinatura": { largura: 1300, altura: 760, html: app("Logon único baseado em SAML", "") + `<div class="sombra"></div><div class="painel">
      <h2>Certificado de Autenticação SAML</h2><p class="sub">Gerenciar o certificado usado pelo Microsoft Entra ID para assinar tokens SAML emitidos para seu aplicativo</p>
      <div class="barra"><span data-n="4">💾 Salvar</span><span>＋ Novo Certificado</span><span>⤒ Importar Certificado</span></div>
      <table><tr><th>Status</th><th>Expiração</th><th>Impressão Digital</th></tr><tr><td class="ok">Ativo</td><td>17/11/2029</td><td class="mono">A1B2C3D4E5F6…</td></tr></table>
      <div class="campo" data-n="1" style="grid-template-columns:200px 1fr;margin-top:22px"><label>Opção de Assinatura</label><div class="caixa">Assinar resposta e declaração SAML ⌄</div></div>
      <div class="campo" data-n="2" style="grid-template-columns:200px 1fr"><label>Algoritmo de Assinatura</label><div class="caixa">SHA-256 ⌄</div></div>
      <p style="font-weight:600;margin:20px 0 6px">Endereços de Email de Notificação</p>
      <div data-n="3"><input value="ti@exemplo.com.br"></div></div>` },

  // 11 · Novo grupo
  "az-11-novo-grupo": { largura: 1100, altura: 680, html: pagina({
    trilha: "Página inicial › Grupos | Todos os grupos › <span>Novo Grupo</span>", titulo: "Novo Grupo", sub: "",
    corpo: `<div class="campo"><label>Tipo de grupo <i>*</i></label><div class="caixa" data-n="1">Segurança ⌄</div></div>
      <div class="campo"><label>Nome do grupo <i>*</i></label><input data-n="2" value="${GRUPOS[1]}"></div>
      <div class="campo"><label>Descrição do grupo</label><input value="Acesso ao Atlas Insights (Keycloak ${REALM})"></div>
      <div class="campo"><label>Funções do Microsoft Entra podem ser atribuídas ao grupo</label><div><span class="chave"><span>Sim</span><span class="on">Não</span></span></div></div>
      <div class="campo"><label>Tipo de associação <i>*</i></label><div class="caixa" data-n="3">Atribuído ⌄</div></div>
      <div class="campo"><label>Proprietários</label><div class="link" data-n="4">1 proprietário selecionado</div></div>
      <div class="campo"><label>Membros</label><div class="link" data-n="5">12 membros selecionados</div></div>
      <div style="margin-top:22px"><span class="botao" data-n="6">Criar</span></div>`,
  }) },

  // 12 · Usuários e grupos
  "az-12-usuarios-grupos": { largura: 1300, html: app("Usuários e grupos", `
      <div class="barra"><span data-n="1">＋ Adicionar usuário/grupo</span><span>✎ Editar atribuição</span><span>🗑 Remover</span><span>☰ Colunas</span></div>
      <p style="color:#605e5c;font-size:13px">O aplicativo aparecerá para os usuários atribuídos em Meus Aplicativos. Defina "visível para os usuários?" como não nas propriedades para impedir isso.</p>
      <table data-n="2"><tr><th>Nome de exibição</th><th>Tipo de objeto</th><th>Função atribuída</th></tr>
      ${GRUPOS.map((g) => `<tr><td>${g}</td><td>Grupo</td><td>Usuário</td></tr>`).join("")}</table>`) },

  // 13 · Propriedades
  "az-13-propriedades": { largura: 1300, altura: 820, html: app("Propriedades", `
      <div class="barra"><span data-n="4">💾 Salvar</span><span>✕ Descartar</span><span>🗑 Excluir</span><span>Tem comentários?</span></div>
      <div class="campo"><label>Habilitar para os usuários entrarem?</label><div><span class="chave"><span class="on">Sim</span><span>Não</span></span></div></div>
      <div class="campo"><label>Nome <i>*</i></label><input value="${APP}"></div>
      <div class="campo"><label>URL de acesso do usuário</label><input class="ro" value="https://launcher.myapps.microsoft.com/api/signin/${APP_ID}?tenantId=…"></div>
      <div class="campo" data-n="1"><label>ID do Aplicativo</label><input class="ro" value="${APP_ID}"></div>
      <div class="campo"><label>ID de objeto</label><input class="ro" value="b81d44c0-…"></div>
      <div class="campo"><label>URL de Resposta</label><input class="ro" value="${ACS}"></div>
      <div class="campo" data-n="2"><label>Atribuição necessária?</label><div><span class="chave"><span class="on">Sim</span><span>Não</span></span></div></div>
      <div class="campo" data-n="3"><label>Visível para os usuários?</label><div><span class="chave"><span class="on">Sim</span><span>Não</span></span></div></div>`) },

  // 14 · Logs de entrada
  "az-14-logs-entrada": { largura: 1300, altura: 720, html: app("Logs de entrada", `
      <div class="barra"><span>⤓ Baixar</span><span>⚙ Exportar Configurações</span><span>↻ Atualizar</span><span>☰ Colunas</span></div>
      <div style="display:flex;gap:10px;margin-bottom:12px"><span class="tag">Data: Últimas 24 horas</span><span class="tag" data-n="1">Aplicativo: ${APP}</span><span class="tag">Status: Falha</span></div>
      <table><tr><th>Data</th><th>Usuário</th><th>Aplicativo</th><th>Status</th><th>Código de erro</th></tr>
      <tr data-n="2"><td>17/11/2026 09:41</td><td>maria.souza@exemplo.com.br</td><td>${APP}</td><td class="erro">Falha</td><td>50105</td></tr>
      <tr><td>17/11/2026 09:38</td><td>joao.lima@exemplo.com.br</td><td>${APP}</td><td class="ok">Êxito</td><td>0</td></tr></table>
      <div class="cartao" style="margin-top:16px" data-n="3"><h3>Detalhes da Atividade: Entradas</h3>
        <div class="kv"><div>Código de erro de entrada</div><div class="mono">50105</div><div>Motivo da falha</div><div class="erro">O usuário conectado 'maria.souza@exemplo.com.br' não está atribuído a uma função do aplicativo.</div>
        <div>Identificador do aplicativo</div><div class="mono">${ENTITY}</div></div></div>`) },
};

(async () => {
  fs.mkdirSync(SAIDA, { recursive: true });
  const navegador = await playwright().chromium.launch();
  const page = await navegador.newPage({ deviceScaleFactor: 1 });
  for (const [nome, { html, largura = 1300, altura = 760 }] of Object.entries(FIGURAS)) {
    await page.setViewportSize({ width: largura, height: altura });
    await page.setContent(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>${CSS}</style></head><body style="position:relative;min-height:${altura}px">${html}</body></html>`);
    await page.evaluate(MARCAR);
    await page.screenshot({ path: path.join(SAIDA, `${nome}.png`), fullPage: true });
    console.log("🖼 ", `${nome}.png`);
  }
  await navegador.close();
})().catch((erro) => {
  console.error("❌", erro.message);
  process.exit(1);
});
