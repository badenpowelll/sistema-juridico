/** Aplicativo instalável (Fase 10): service worker, notificações no celular e voz. Tudo opcional e só no navegador. */
import { api, enviar } from "@/lib/api";

export type AparelhoPush = { id: string; dispositivo: string | null; servico: string; so_urgentes: boolean; falhas: number;
  ultimo_envio_em: string | null; criado_em: string; este_aparelho: boolean };
export type EstadoPush = { disponivel: boolean; chave_publica: string | null; estado: string; aviso: string; aparelhos: AparelhoPush[] };

export const suportaSW = () => typeof window !== "undefined" && "serviceWorker" in navigator;
export const suportaPush = () => suportaSW() && "PushManager" in window && "Notification" in window;

export async function registrarSW(): Promise<ServiceWorkerRegistration | null> {
  if (!suportaSW()) return null;
  try { return await navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }); } catch { return null; }
}

/** Ao sair: apaga o que o service worker guardou (só arquivos públicos, mas não precisa ficar). */
export async function limparAparelho() {
  if (!suportaSW()) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    reg?.active?.postMessage("limpar");
    const sub = await reg?.pushManager?.getSubscription();
    await sub?.unsubscribe();
    // desliga o service worker e apaga os arquivos guardados; ele volta a ser registrado no próximo acesso ao painel
    await reg?.unregister();
    await apagarCaches();
  } catch { /* navegador sem suporte: nada a limpar */ }
}

async function apagarCaches() {
  if ("caches" in window) await Promise.all((await caches.keys()).map((k) => caches.delete(k)));
}

/** Na página de entrada: sem service worker registrado (saiu), apaga o que uma cópia em andamento ainda tenha gravado. */
export async function limparSobras() {
  if (!suportaSW()) return;
  try { if (!(await navigator.serviceWorker.getRegistration())) await apagarCaches(); } catch { /* nada a limpar */ }
}

function chaveBytes(b64: string): Uint8Array<ArrayBuffer> {
  const s = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(s.length));
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

export function nomeDoAparelho(ua = typeof navigator !== "undefined" ? navigator.userAgent : ""): string {
  const so = /Android/i.test(ua) ? "Android" : /iPhone|iPad/i.test(ua) ? "iPhone/iPad" : /Windows/i.test(ua) ? "Windows"
    : /Mac OS/i.test(ua) ? "Mac" : /Linux/i.test(ua) ? "Linux" : "Aparelho";
  const nav = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "navegador";
  return `${nav} no ${so}`;
}

export async function ativarPush(chavePublica: string, soUrgentes: boolean): Promise<AparelhoPush> {
  if (!suportaPush()) throw new Error("Este navegador não recebe notificações. No iPhone, instale o EJMF na tela de início antes.");
  const permissao = await Notification.requestPermission();
  if (permissao !== "granted") throw new Error("Permissão de notificação negada neste navegador.");
  const reg = (await navigator.serviceWorker.getRegistration()) ?? (await registrarSW());
  if (!reg) throw new Error("Não foi possível preparar o aplicativo neste navegador.");
  await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chaveBytes(chavePublica) });
  const j = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } };
  return enviar<AparelhoPush>("/aparelhos/push", "POST", { endpoint: j.endpoint, keys: j.keys, dispositivo: nomeDoAparelho(), so_urgentes: soUrgentes });
}

export const estadoPush = () => api<EstadoPush>("/aparelhos/push");

/** Reconhecimento de voz do navegador (Web Speech API), quando existe. */
type Reconhecedor = { lang: string; interimResults: boolean; maxAlternatives: number; start: () => void; stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null };
export function criarReconhecedor(): Reconhecedor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, new () => Reconhecedor>;
  const C = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  if (!C) return null;
  const r = new C();
  r.lang = "pt-BR"; r.interimResults = false; r.maxAlternatives = 1;
  return r;
}

export function falar(texto: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window) || !texto) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(texto.slice(0, 600));
  u.lang = "pt-BR";
  window.speechSynthesis.speak(u);
}
