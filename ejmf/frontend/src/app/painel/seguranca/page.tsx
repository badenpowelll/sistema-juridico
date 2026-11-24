"use client";
import QRCode from "qrcode";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";

type SessaoInfo = { id: string; criado_em: string; ultimo_uso_em: string; ip: string | null; agente: string | null; atual: boolean };

export default function Seguranca() {
  const { eu, recarregar } = useEu();
  const [config, setConfig] = useState<{ segredo: string; uri: string; qr: string } | null>(null);
  const [sessoes, setSessoes] = useState<SessaoInfo[]>([]);
  const [msg, setMsg] = useState<{ tom: string; texto: string } | null>(null);
  const carregarSessoes = () => api<SessaoInfo[]>("/auth/sessoes").then(setSessoes).catch(() => {});
  useEffect(() => { carregarSessoes(); }, []);

  async function iniciarMfa() {
    try {
      const r = await enviar<{ segredo: string; uri: string }>("/auth/mfa/configurar", "POST");
      setConfig({ ...r, qr: await QRCode.toDataURL(r.uri, { margin: 1, width: 200 }) });
    } catch (e) { setMsg({ tom: "perigo", texto: (e as Error).message }); }
  }
  async function ativarMfa(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await enviar("/auth/mfa/ativar", "POST", { codigo: new FormData(e.currentTarget).get("codigo") });
      setConfig(null); setMsg({ tom: "ok", texto: "Verificação em duas etapas ativada. As outras sessões foram encerradas." });
      recarregar(); carregarSessoes();
    } catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }
  async function trocarSenha(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      const r = await enviar<{ sessoes_revogadas: number }>("/auth/senha", "POST", { senha_atual: f.get("senha_atual"), senha_nova: f.get("senha_nova") });
      setMsg({ tom: "ok", texto: `Senha alterada. ${r.sessoes_revogadas} outra(s) sessão(ões) encerrada(s).` });
      e.currentTarget.reset(); carregarSessoes();
    } catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }
  async function revogar(id: string) { await enviar(`/auth/sessoes/${id}`, "DELETE"); carregarSessoes(); }
  async function revogarOutras() { await enviar("/auth/sessoes/revogar-outras", "POST"); carregarSessoes(); }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Minha segurança</h1>
      {eu.mfa_obrigatorio && !eu.mfa_ativo && <Aviso tom="alerta">Para continuar, ative a verificação em duas etapas.</Aviso>}
      {msg && <Aviso tom={msg.tom}>{msg.texto}</Aviso>}

      <Cartao titulo="Verificação em duas etapas" acao={eu.mfa_ativo ? <Selo tom="ok">Ativa</Selo> : <Selo tom="alerta">Inativa</Selo>}>
        {eu.mfa_ativo ? <p className="text-sm text-suave">Seu acesso exige o código do aplicativo autenticador.</p> : config ? (
          <div className="flex flex-col gap-4 sm:flex-row">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={config.qr} alt="QR code para o aplicativo autenticador" width={200} height={200} className="rounded bg-white p-2" />
            <form onSubmit={ativarMfa} className="flex flex-1 flex-col gap-3">
              <p className="text-sm text-suave">Leia o QR code no aplicativo autenticador ou digite a chave: <code className="break-all">{config.segredo}</code></p>
              <Campo id="codigo-mfa" name="codigo" rotulo="Código de 6 dígitos" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required />
              <Botao type="submit">Ativar</Botao>
            </form>
          </div>
        ) : <Botao onClick={iniciarMfa}>Configurar agora</Botao>}
      </Cartao>

      <Cartao titulo="Sessões abertas" acao={<Botao variante="perigo" onClick={revogarOutras}>Encerrar as outras</Botao>}>
        <ul className="divide-y divide-borda">
          {sessoes.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <div><div>{s.agente ?? "Navegador"} {s.atual && <Selo tom="ok">Esta sessão</Selo>}</div>
                <div className="text-xs text-suave">IP {s.ip ?? "—"} · último uso {dataHora(s.ultimo_uso_em)}</div></div>
              {!s.atual && <Botao variante="secundario" onClick={() => revogar(s.id)}>Encerrar</Botao>}
            </li>
          ))}
        </ul>
      </Cartao>

      <Cartao titulo="Trocar senha">
        <form onSubmit={trocarSenha} className="grid gap-3 sm:grid-cols-3 sm:items-end">
          <Campo id="senha_atual" name="senha_atual" type="password" rotulo="Senha atual" autoComplete="current-password" required />
          <Campo id="senha_nova" name="senha_nova" type="password" rotulo="Nova senha" minLength={12} autoComplete="new-password" required ajuda="Mínimo de 12 caracteres." />
          <Botao type="submit">Alterar</Botao>
        </form>
      </Cartao>
    </div>
  );
}
