// Prints da tela Metodologia (media/metodologia/*.png): percorre o uso real do assistente num realm de
// demonstração (demo-sso), marca com números vermelhos os pontos citados no passo a passo e apaga o realm no fim.
//
//   make prints        (com o compose no ar; usa KC_HOST, ASSISTENTE_HOST, KC_ADMIN_* e KC_REALM_ADMIN_* do .env)
//
// Precisa do playwright-core (o make prints baixa pelo npx) e do Chromium dele (npx playwright install chromium).
const fs = require("fs");
const os = require("os");
const path = require("path");

function playwright() {
  try {
    return require("playwright-core");
  } catch {
    // Instalado pelo npx (make prints): fica no cache ~/.npm/_npx/<hash>/node_modules
    const cache = path.join(os.homedir(), ".npm", "_npx");
    for (const dir of fs.existsSync(cache) ? fs.readdirSync(cache) : []) {
      const candidato = path.join(cache, dir, "node_modules", "playwright-core");
      if (fs.existsSync(candidato)) return require(candidato);
    }
    throw new Error("playwright-core não encontrado: rode pelo make prints.");
  }
}

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0"; // certificados locais (~/.certs)
const KC = `https://${process.env.KC_HOST || "keycloak.docker.localhost"}`;
const APP = `https://${process.env.ASSISTENTE_HOST || "keycloak-assistente.docker.localhost"}`;
const REALM = "demo-sso";
const SAIDA = path.join(__dirname, "..", "media", "metodologia");
const METADATA = "http://localhost:8080/realms/master/protocol/saml/descriptor"; // o master faz o papel do Entra

async function admin(metodo, caminho, corpo) {
  const token = await fetch(`${KC}/realms/master/protocol/openid-connect/token`, {
    method: "POST",
    body: new URLSearchParams({ grant_type: "password", client_id: "admin-cli", username: process.env.KC_ADMIN_USER, password: process.env.KC_ADMIN_PASSWORD }),
  }).then((r) => r.json());
  const r = await fetch(`${KC}/admin/realms${caminho}`, {
    method: metodo,
    headers: { Authorization: `Bearer ${token.access_token}`, "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

// Números vermelhos sobre os elementos, como nas figuras do README_sso.md
async function marcar(page, marcas) {
  await page.evaluate((marcas) => {
    document.querySelectorAll(".print-marca").forEach((m) => m.remove());
    for (const [seletor, numero] of marcas) {
      const alvo = document.querySelector(seletor);
      if (!alvo) continue;
      const caixa = alvo.getBoundingClientRect();
      const borda = document.createElement("div");
      borda.className = "print-marca";
      Object.assign(borda.style, {
        position: "absolute", left: `${caixa.left + scrollX - 3}px`, top: `${caixa.top + scrollY - 3}px`,
        width: `${caixa.width + 6}px`, height: `${caixa.height + 6}px`, border: "2px solid #e11d48",
        borderRadius: "8px", zIndex: 99998, pointerEvents: "none",
      });
      const bola = document.createElement("div");
      bola.className = "print-marca";
      bola.textContent = numero;
      Object.assign(bola.style, {
        position: "absolute", left: `${caixa.left + scrollX - 14}px`, top: `${caixa.top + scrollY - 14}px`,
        width: "24px", height: "24px", borderRadius: "50%", background: "#e11d48", color: "#fff",
        font: "700 13px/24px Inter, sans-serif", textAlign: "center", zIndex: 99999, pointerEvents: "none",
      });
      document.body.append(borda, bola);
    }
  }, marcas);
}

async function print(page, arquivo, marcas = [], inteira = true) {
  // O django-debug-toolbar (DEBUG=true no compose) fica fora dos prints
  await page.addStyleTag({ content: "#djDebug { display: none !important; }" });
  await marcar(page, marcas);
  await page.screenshot({ path: path.join(SAIDA, arquivo), fullPage: inteira });
  await marcar(page, []);
  console.log("📸", arquivo);
}

(async () => {
  fs.mkdirSync(SAIDA, { recursive: true });
  await admin("DELETE", `/${REALM}`);
  const navegador = await playwright().chromium.launch();
  const contexto = await navegador.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1360, height: 860 }, locale: "pt-BR" });
  const page = await contexto.newPage();
  page.on("dialog", (d) => d.accept());
  const ir = (tela) => page.goto(`${APP}${tela}`, { waitUntil: "networkidle" });
  const aplicar = async (valor = "aplicar") => {
    await page.click(`button[value=${valor}]`);
    await page.waitForSelector("#plano");
  };

  // Entrada e login
  await ir("/");
  await print(page, "01-entrada.png", [[".app-publica .ct-btn--primario", 1]], false);
  await ir("/login");
  await page.waitForSelector("#username");
  await page.fill("#username", process.env.KC_REALM_ADMIN_USER || "admin");
  await print(page, "02-login.png", [["#username", 1], ["#password", 2], ["#kc-login", 3]], false);
  await page.fill("#password", process.env.KC_REALM_ADMIN_PASSWORD || "admin");
  await page.click("#kc-login");
  await page.waitForURL(`${APP}/app/**`);

  // Painel
  await ir("/app/painel/");
  await print(page, "03-painel.png", [["#realm-ativo", 1], [".app-nav", 2], [".ct-header .ct-btn--primario", 3]]);

  // Etapa 1
  await ir("/app/realm/?novo=1");
  await page.fill("#id_realm", REALM);
  await page.fill("#id_nome_exibicao", "Demo SSO");
  for (const [i, [cid, nome]] of [["atlas-insights", "Atlas Insights"]].entries()) {
    await page.fill(`#id_apps-${i}-client_id`, cid);
    await page.fill(`#id_apps-${i}-nome`, nome);
    await page.fill(`#id_apps-${i}-url`, `https://${cid}.docker.localhost`);
  }
  await print(page, "04-realm-formulario.png", [["#id_realm", 1], ["table.ct-table", 2], ["button[value=simular]", 3], ["button[value=aplicar]", 4]]);
  await aplicar("simular");
  await print(page, "05-realm-simulacao.png", [["#plano", 1], ["button[value=aplicar]", 2]]);
  // Segunda linha de app só agora, para mostrar que a tela ganha linhas
  await aplicar();
  await page.fill("#id_apps-1-client_id", "mongo-migrator");
  await page.fill("#id_apps-1-nome", "Mongo Migrator");
  await page.fill("#id_apps-1-url", "https://mongo-migrator.docker.localhost");
  await aplicar();
  await print(page, "06-realm-aplicado.png", [["#plano", 1], ["#realm-ativo", 2]]);

  // Etapa 2
  await ir("/app/grupos/");
  await print(page, "07-grupos.png", [["form table.ct-table", 1], [".ct-header .ct-btn", 2], ["button[value=aplicar]", 3]]);
  await aplicar();

  // Etapa 3
  await ir("/app/sso/");
  await page.fill("#id_alias", "entra");
  await page.dispatchEvent("#id_alias", "input");
  await print(page, "08-sso-urls.png", [["#url-entity", 1], ["#url-acs", 2], ["[data-copiar=url-acs]", 3]], false);
  await page.locator("details").first().scrollIntoViewIfNeeded();
  await print(page, "09-sso-roteiro.png", [["details[open]", 1]], false);
  await page.fill("#id_metadata_url", METADATA);
  await page.locator("#cadastro").scrollIntoViewIfNeeded();
  await print(page, "10-sso-formulario.png", [["#id_tipo", 1], ["#id_alias", 2], ["#id_metadata_url", 3], ["#id_login_direto", 4]], false);
  await aplicar();
  await print(page, "11-sso-aplicado.png", [["#plano", 1]]);

  // Etapa 4
  await ir("/app/mapeamento/");
  await print(page, "12-mapeamento.png", [["form table.ct-table", 1], ['input[name="map-0-valor"]', 2], ['input[name="map-0-chave"]', 3]]);
  await aplicar();

  // Um usuário "vindo do SSO" no grupo do Atlas, para a consulta da etapa 5
  await admin("POST", `/${REALM}/users`, { username: "maria.souza", email: "maria.souza@empresa.com.br", firstName: "Maria", lastName: "Souza", enabled: true });
  const [maria] = await admin("GET", `/${REALM}/users?username=maria.souza&exact=true`);
  const [grupo] = await admin("GET", `/${REALM}/groups?search=${REALM}-atlas-insights&exact=true`);
  await admin("PUT", `/${REALM}/users/${maria.id}/groups/${grupo.id}`);
  await admin("POST", `/${REALM}/users`, { username: "joao.antigo", enabled: true });

  // Etapa 5
  await ir("/app/conferir/");
  await print(page, "13-conferir.png", [[".ct-kpis", 1], [".ct-header .ct-btn", 2]]);
  await ir("/app/conferir/?usuario=maria");
  await page.locator("#usuario").scrollIntoViewIfNeeded();
  await print(page, "14-conferir-usuario.png", [["#usuario", 1], [".ct-card:has(#usuario) table", 2], ["[data-copiar=env-1]", 3]], false);

  // Migração
  await ir("/app/migracao/?vm=root%40vm-antiga&container=keycloak&destino=compose");
  await print(page, "15-migracao-comandos.png", [[".ct-filters", 1], ["#cmd-vm", 2], ["#cmd-a", 3], ["#cmd-b", 4]], false);
  // O formulário do host posta na mesma URL: com ?incompletos=1 a página traz as duas respostas
  await ir("/app/migracao/?incompletos=1");
  await page.fill("#id_antigo", "https://atlas-insights.docker.localhost");
  await page.fill("#id_novo", "https://atlas.empresa.com.br");
  await aplicar("simular");
  await print(page, "16-migracao-host.png", [["#plano", 1], ["#id_antigo", 2], ["button[value=aplicar]", 3]]);
  await page.locator("a[href='?incompletos=1']").scrollIntoViewIfNeeded();
  await print(page, "17-migracao-incompletos.png", [["a[href='?incompletos=1']", 1], [".ct-card:has(a[href='?incompletos=1']) table", 2]], false);

  // Histórico e painel final
  await ir("/app/historico/");
  const primeiro = await page.locator("tbody a").first().getAttribute("href");
  await ir(`/app/historico/${primeiro}`);
  await print(page, "18-historico.png", [[".ct-info", 1], ["#plano", 2]]);
  await ir("/app/painel/");
  await print(page, "19-painel-final.png", [[".ct-card", 1]]);

  await navegador.close();
  await admin("DELETE", `/${REALM}`);
  console.log(`✅ Prints em ${SAIDA}; realm ${REALM} apagado.`);
})().catch(async (erro) => {
  console.error("❌", erro.message);
  await admin("DELETE", `/${REALM}`).catch(() => {});
  process.exit(1);
});
