/* Service worker do EJMF (Fase 10, ADR-0014).
 * Guarda no aparelho SÓ arquivos públicos e imutáveis do aplicativo (scripts e estilos com hash, ícones) e a página
 * "Sem conexão". Nunca guarda respostas da API, páginas do painel, documentos ou downloads: dado de cliente não fica
 * no celular. Notificações chegam sem conteúdo (só "Nova notificação no EJMF") e abrem o sistema, que pede login. */
const VERSAO = "ejmf-v1";
const OFFLINE = "/offline";
const PRECACHE = [OFFLINE, "/icones/icone-192.png", "/icones/icone-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSAO).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const estatico = (url) => url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icones/");

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return; // API: sempre direto na rede
  if (estatico(url)) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => {
      if (r.ok && r.type === "basic") { const copia = r.clone(); caches.open(VERSAO).then((c) => c.put(req, copia)); }
      return r;
    })));
    return;
  }
  if (req.mode === "navigate") {
    // páginas sempre da rede; sem conexão, mostra a página "Sem conexão" (nenhuma página com dados fica guardada)
    e.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  }
});

self.addEventListener("message", (e) => {
  if (e.data === "limpar") e.waitUntil(caches.keys().then((ks) => Promise.all(ks.map((k) => caches.delete(k)))));
});

self.addEventListener("push", (e) => {
  let d = { titulo: "Nova notificação no EJMF", texto: "Abra o sistema para ver.", link: "/painel" };
  try { if (e.data) d = { ...d, ...e.data.json() }; } catch { /* corpo inválido: mantém o aviso genérico */ }
  const link = typeof d.link === "string" && d.link.startsWith("/") ? d.link : "/painel";
  e.waitUntil(self.registration.showNotification(d.titulo, {
    body: d.texto, icon: "/icones/icone-192.png", badge: "/icones/icone-192.png", tag: "ejmf", renotify: true, data: { link },
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const alvo = new URL(e.notification.data?.link || "/painel", self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((js) => {
    for (const j of js) if (j.url.startsWith(self.location.origin)) return j.navigate(alvo).then((w) => (w || j).focus());
    return self.clients.openWindow(alvo);
  }));
});
