"use client";
import { useCallback, useEffect, useState } from "react";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";

type Copia = {
  id: string; situacao: string; origem: string; iniciada_em: string; concluida_em: string | null; arquivo: string | null;
  tamanho: number | null; sha256: string | null; chave_id: string | null; erro: string | null; teste_situacao: string | null;
  testada_em: string | null; expirada_em: string | null;
  manifesto: { revisao: string; total_linhas: number; arquivos: number; arquivos_bytes: number; banco_tamanho: number } | null;
  teste_detalhes: { erro?: string; segundos?: number; linhas?: number; tabelas?: number; arquivos_conferidos?: number;
    auditoria_integra?: boolean } | null;
};
type Estado = {
  configurada: boolean; comprometido: boolean; motivos: string[]; ultima_concluida_em: string | null; ultimo_teste_em: string | null;
  ultimo_teste: string | null; retencao: { diarias: number; semanais: number; mensais: number }; hora: string; teste_dias: number;
  externa: string; espaco_livre_bytes: number | null; copias: Copia[]; pode_executar: boolean;
};

const SITUACAO: Record<string, [string, string]> = {
  executando: ["Em andamento", "info"], concluida: ["Concluída", "ok"], falhou: ["Falhou", "perigo"], expirada: ["Apagada pela retenção", "neutro"],
};
const ORIGEM: Record<string, string> = { agendador: "Agendada", pessoa: "Pedida na tela", funcao: "Função virtual" };

function tamanho(b: number | null | undefined) {
  if (b === null || b === undefined) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = b;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${u[i]}`;
}

export default function CopiasDeSeguranca() {
  const [e, setE] = useState<Estado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(() => { api<Estado>("/backups").then(setE).catch((x) => setErro(x.message)); }, []);
  useEffect(() => { carregar(); }, [carregar]);

  async function pedir(caminho: string) {
    setErro(null); setOk(null); setOcupado(true);
    try { setOk((await enviar<{ mensagem: string }>(caminho, "POST")).mensagem); }
    catch (x) { setErro((x as Error).message); }
    finally { setOcupado(false); carregar(); }
  }

  if (erro && !e) return <Aviso>{erro}</Aviso>;
  if (!e) return <p className="text-suave" aria-busy="true">Carregando…</p>;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Cópias de segurança</h1>
        <p className="text-sm text-suave">Banco e arquivos, cifrados com uma chave que fica fora do sistema. Cópia sem teste de restauração não é confiável.</p>
      </div>
      <div role="status" data-comprometido={e.comprometido}
        className={`rounded-xl border px-4 py-3 text-sm ${!e.configurada ? "border-alerta/50 bg-alerta/10" : e.comprometido ? "border-perigo/50 bg-perigo/10 text-perigo" : "border-ok/40 bg-ok/10"}`}>
        <p className="font-semibold">{!e.configurada ? "Aguardando configuração" : e.comprometido ? "Precisam de atenção" : "Em dia"}</p>
        {e.motivos.length > 0 && <ul className="mt-1 list-disc pl-5">{e.motivos.map((m) => <li key={m}>{m}</li>)}</ul>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      <div className="grid gap-5 lg:grid-cols-2">
        <Cartao titulo="Como funciona" acao={e.pode_executar && e.configurada ? <Botao disabled={ocupado} onClick={() => pedir("/backups")}>Fazer cópia agora</Botao> : undefined}>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-suave">Cópia diária</dt><dd>a partir das {e.hora}</dd>
            <dt className="text-suave">Teste de restauração</dt><dd>a cada {e.teste_dias} dias, num banco descartável</dd>
            <dt className="text-suave">Guardadas</dt><dd>{e.retencao.diarias} diárias, {e.retencao.semanais} semanais e {e.retencao.mensais} mensais</dd>
            <dt className="text-suave">Última cópia</dt><dd>{e.ultima_concluida_em ? dataHora(e.ultima_concluida_em) : "nenhuma"}</dd>
            <dt className="text-suave">Último teste</dt><dd>{e.ultimo_teste_em ? `${dataHora(e.ultimo_teste_em)} (${e.ultimo_teste === "aprovado" ? "aprovado" : "reprovado"})` : "nunca"}</dd>
            <dt className="text-suave">Espaço livre</dt><dd>{tamanho(e.espaco_livre_bytes)}</dd>
            <dt className="text-suave">Cópia em outro provedor</dt><dd>{e.externa}</dd>
          </dl>
          {!e.configurada && (
            <p className="mt-3 text-sm text-suave">Para ligar: no servidor, rode <code>python -m app.cli gerar-chave-backup</code>, coloque a chave em
              <code> EJMF_BACKUP_CHAVE</code> e guarde uma cópia dela fora do servidor. Sem a chave, nenhuma cópia pode ser aberta.</p>
          )}
          <p className="mt-3 text-xs text-suave">Por segurança, a cópia não é baixada pela tela, e restaurar é feito só no servidor, num banco vazio (ver BACKUP.md).</p>
        </Cartao>
      </div>

      <Cartao titulo="Histórico">
        {e.copias.length === 0 ? <p className="text-sm text-suave">Nenhuma cópia ainda.</p> : (
          <ul className="divide-y divide-borda text-sm" aria-label="Cópias de segurança">
            {e.copias.map((c) => (
              <li key={c.id} className="flex flex-col gap-1 py-3" data-copia={c.situacao}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{dataHora(c.iniciada_em)}</span>
                  <Selo tom={SITUACAO[c.situacao]?.[1] ?? "neutro"}>{SITUACAO[c.situacao]?.[0] ?? c.situacao}</Selo>
                  {c.teste_situacao && <Selo tom={c.teste_situacao === "aprovado" ? "ok" : "perigo"}>Restauração {c.teste_situacao}</Selo>}
                  <span className="text-xs text-suave">{ORIGEM[c.origem] ?? c.origem}</span>
                  {e.pode_executar && c.situacao === "concluida" && (
                    <Botao variante="secundario" disabled={ocupado} onClick={() => pedir(`/backups/${c.id}/testar`)}>Testar restauração</Botao>
                  )}
                </div>
                {c.manifesto && <p className="text-xs text-suave">{tamanho(c.tamanho)} · {c.manifesto.total_linhas.toLocaleString("pt-BR")} registros · {c.manifesto.arquivos} arquivo(s) ({tamanho(c.manifesto.arquivos_bytes)}) · banco na versão {c.manifesto.revisao}</p>}
                {c.sha256 && <p className="break-all font-mono text-[11px] text-suave">SHA-256 {c.sha256}</p>}
                {c.teste_detalhes && !c.teste_detalhes.erro && <p className="text-xs">Restaurada em {c.teste_detalhes.segundos} s: {c.teste_detalhes.tabelas} tabelas, {c.teste_detalhes.linhas?.toLocaleString("pt-BR")} registros e {c.teste_detalhes.arquivos_conferidos} arquivo(s) conferidos; cadeia de auditoria {c.teste_detalhes.auditoria_integra ? "íntegra" : "com problema"}.</p>}
                {c.teste_detalhes?.erro && <p className="text-xs text-perigo">Teste: {c.teste_detalhes.erro}</p>}
                {c.erro && <p className="text-xs text-perigo">{c.erro}</p>}
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
