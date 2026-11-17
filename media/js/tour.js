// Tour explicativo das telas: destaca cada parte da tela, explica e mostra uma figura.
//
// Os passos vêm do servidor (keycloak/screens/config/tours.py) em <script id="tour-dados">.
// Cada passo: { alvo, titulo, texto, figura, legenda }. "alvo" é um seletor CSS; com "|texto",
// escolhe entre os que casam o primeiro que contém esse texto (ex.: "section|Últimas ações").
// Sem alvo, ou se o alvo não estiver na tela (ex.: só aparece depois de simular), o passo
// aparece no centro.
//
// Abre pelo botão "Tour" do topo, por ?tour=1 na URL, ou pelo convite da primeira visita.
(function () {
  const dados = document.getElementById("tour-dados");
  if (!dados) return;
  const tour = JSON.parse(dados.textContent);
  if (!tour || !tour.passos || !tour.passos.length) return;
  const chave = `tour-visto:${tour.tela}`;

  let atual = 0;
  let camada, destaque, balao;

  function guardar(valor) {
    try { localStorage.setItem(chave, valor); } catch (e) { /* navegação privada: só não lembra */ }
  }
  function visto() {
    try { return localStorage.getItem(chave); } catch (e) { return "1"; }
  }

  function achar(alvo) {
    if (!alvo) return null;
    const [seletor, texto] = alvo.split("|");
    let lista;
    try { lista = [...document.querySelectorAll(seletor)]; } catch (e) { return null; }
    lista = lista.filter((el) => el.offsetParent !== null || el.getClientRects().length);
    if (texto) lista = lista.filter((el) => el.textContent.includes(texto));
    return lista[0] || null;
  }

  function montar() {
    camada = document.createElement("div");
    camada.className = "tour-camada";
    camada.addEventListener("click", fechar);
    destaque = document.createElement("div");
    destaque.className = "tour-destaque";
    balao = document.createElement("div");
    balao.className = "tour-balao";
    balao.setAttribute("role", "dialog");
    balao.setAttribute("aria-modal", "true");
    document.body.append(camada, destaque, balao);
    document.addEventListener("keydown", teclas);
    window.addEventListener("resize", posicionar);
    window.addEventListener("scroll", posicionar, { passive: true });
  }

  function desmontar() {
    [camada, destaque, balao].forEach((el) => el && el.remove());
    camada = destaque = balao = null;
    document.removeEventListener("keydown", teclas);
    window.removeEventListener("resize", posicionar);
    window.removeEventListener("scroll", posicionar);
  }

  function teclas(e) {
    if (e.key === "Escape") fechar();
    else if (e.key === "ArrowRight") ir(atual + 1);
    else if (e.key === "ArrowLeft") ir(atual - 1);
  }

  function escapar(texto) {
    const div = document.createElement("div");
    div.textContent = texto || "";
    return div.innerHTML;
  }

  function desenhar() {
    const passo = tour.passos[atual];
    const ultimo = atual === tour.passos.length - 1;
    const figura = passo.figura
      ? `<a class="tour-figura" href="${passo.figura}" target="_blank" rel="noopener" title="Abrir em tamanho real"><img src="${passo.figura}" alt="${escapar(passo.legenda || passo.titulo)}"></a>` +
        (passo.legenda ? `<p class="tour-legenda">${escapar(passo.legenda)}</p>` : "")
      : "";
    // "texto" vem do tours.py (conteúdo nosso, com <b>, <code> e links): entra como HTML.
    balao.innerHTML = `
      <div class="tour-cabeca"><span class="tour-contador">${atual + 1} de ${tour.passos.length}</span>
        <button type="button" class="tour-x" aria-label="Fechar o tour">&times;</button></div>
      <h3 class="tour-titulo">${escapar(passo.titulo)}</h3>
      <div class="tour-texto">${passo.texto}</div>
      ${figura}
      <div class="tour-barra"><div class="tour-pontos">${tour.passos.map((_, i) => `<span class="${i === atual ? "on" : ""}"></span>`).join("")}</div>
        <div class="tour-botoes">
          ${atual > 0 ? '<button type="button" class="ct-btn ct-btn--pequeno" data-tour="voltar">Anterior</button>' : ""}
          <button type="button" class="ct-btn ct-btn--pequeno ct-btn--primario" data-tour="avancar">${ultimo ? "Concluir" : "Próximo"}</button>
        </div></div>`;
    balao.setAttribute("aria-label", passo.titulo);
    balao.querySelector(".tour-x").addEventListener("click", fechar);
    balao.querySelector('[data-tour="avancar"]').addEventListener("click", () => (ultimo ? concluir() : ir(atual + 1)));
    balao.querySelector('[data-tour="voltar"]')?.addEventListener("click", () => ir(atual - 1));
    const img = balao.querySelector("img");
    if (img) img.addEventListener("load", posicionar);
    balao.querySelector('[data-tour="avancar"]').focus({ preventScroll: true });
  }

  function posicionar() {
    if (!balao) return;
    const alvo = achar(tour.passos[atual].alvo);
    const margem = 12;
    const largura = Math.min(420, window.innerWidth - 2 * margem);
    balao.style.width = `${largura}px`;
    if (!alvo) {
      destaque.style.display = "none";
      camada.classList.add("tour-camada--escura");
      balao.style.left = `${(window.innerWidth - largura) / 2}px`;
      balao.style.top = `${Math.max(margem, (window.innerHeight - balao.offsetHeight) / 2)}px`;
      return;
    }
    camada.classList.remove("tour-camada--escura");
    const r = alvo.getBoundingClientRect();
    Object.assign(destaque.style, {
      display: "block", left: `${r.left - 6}px`, top: `${r.top - 6}px`, width: `${r.width + 12}px`, height: `${r.height + 12}px`,
    });
    const altura = balao.offsetHeight;
    // Embaixo do alvo; se não couber, em cima; se não couber, ao lado; senão, no rodapé da tela.
    let top = r.bottom + margem;
    if (top + altura > window.innerHeight - margem) top = r.top - altura - margem;
    let left = Math.min(Math.max(margem, r.left), window.innerWidth - largura - margem);
    if (top < margem) {
      top = Math.max(margem, Math.min(r.top, window.innerHeight - altura - margem));
      left = r.right + margem + largura < window.innerWidth ? r.right + margem : Math.max(margem, r.left - largura - margem);
    }
    balao.style.left = `${left}px`;
    balao.style.top = `${top}px`;
  }

  function ir(indice) {
    if (indice < 0 || indice >= tour.passos.length) return;
    atual = indice;
    desenhar();
    const alvo = achar(tour.passos[atual].alvo);
    if (alvo) {
      alvo.scrollIntoView({ block: "center", behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
    }
    requestAnimationFrame(posicionar);
  }

  function abrir(indice = 0) {
    document.querySelector(".tour-convite")?.remove();
    if (!balao) montar();
    ir(indice);
  }

  function fechar() {
    guardar("1");
    desmontar();
  }

  function concluir() {
    guardar("1");
    desmontar();
  }

  function convidar() {
    const botao = document.querySelector("[data-tour-abrir]");
    if (!botao) return;
    const convite = document.createElement("div");
    convite.className = "tour-convite";
    convite.innerHTML = `<p><b>Primeira vez nesta tela?</b> Um tour de ${tour.passos.length} passos mostra o que cada parte faz.</p>
      <div class="tour-botoes"><button type="button" class="ct-btn ct-btn--pequeno" data-agora-nao>Agora não</button>
      <button type="button" class="ct-btn ct-btn--pequeno ct-btn--primario" data-comecar>Fazer o tour</button></div>`;
    document.body.append(convite);
    const r = botao.getBoundingClientRect();
    convite.style.top = `${r.bottom + 10}px`;
    convite.style.right = `${Math.max(12, window.innerWidth - r.right)}px`;
    convite.querySelector("[data-comecar]").addEventListener("click", () => abrir(0));
    convite.querySelector("[data-agora-nao]").addEventListener("click", () => { guardar("1"); convite.remove(); });
  }

  document.querySelectorAll("[data-tour-abrir]").forEach((b) => b.addEventListener("click", () => abrir(0)));
  const params = new URLSearchParams(location.search);
  if (params.get("tour") === "1") abrir(0);
  else if (!visto() && !navigator.webdriver) convidar();
  window.tourDaTela = { abrir, fechar };
})();
