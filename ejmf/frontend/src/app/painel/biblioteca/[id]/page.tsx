"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { MOTIVO_VERSAO_ITEM, TOM_VIGENCIA, type Colecao, type DetalheItem } from "@/lib/conhecimento";

type Diff = { a: number; b: number; diferencas: string[]; iguais: boolean; truncado: boolean };

export default function ItemBiblioteca() {
  const { id } = useParams<{ id: string }>();
  const [i, setI] = useState<DetalheItem | null>(null);
  const [colecoes, setColecoes] = useState<Colecao[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cmp, setCmp] = useState<Diff | null>(null);
  const [verTexto, setVerTexto] = useState<{ numero: number; texto: string } | null>(null);
  const [novoTexto, setNovoTexto] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api<DetalheItem>(`/biblioteca/${id}`).then(setI).catch((e) => setErro(e.message));
    api<{ itens: Colecao[] }>("/conhecimento/colecoes").then((r) => setColecoes(r.itens)).catch(() => {});
  }, [id]);

  async function acao(fn: () => Promise<DetalheItem | { item: DetalheItem; resultado: Record<string, unknown> }>, msg: string) {
    setErro(null); setOk(null); setOcupado(true);
    try {
      const r = await fn();
      if ("item" in r) {
        setI(r.item);
        const res = r.resultado as { alterado?: boolean; erro?: string; versao?: number };
        setOk(res.erro ? null : res.alterado ? `Texto novo coletado (versão ${res.versao}). Confira antes de usar.` : "A fonte não mudou desde a última coleta.");
        if (res.erro) setErro(`Fonte indisponível: ${res.erro}`);
      } else { setI(r); setOk(msg); }
    } catch (x) { setErro((x as Error).message); }
    setOcupado(false);
  }

  if (!i) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  const recarregar = () => api<DetalheItem>(`/biblioteca/${id}`);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/biblioteca" className="text-sm text-dourado hover:underline">← Biblioteca</Link>
        <h1 className="font-serif text-3xl font-semibold">{i.titulo}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-suave">
          <Selo tom={TOM_VIGENCIA[i.vigencia] ?? "neutro"}>{i.vigencia_rotulo}</Selo>
          <Selo>{i.tipo_rotulo}</Selo>
          <Selo>{i.licenca_rotulo}</Selo>
          {i.situacao === "arquivado" && <Selo tom="neutro">Arquivado</Selo>}
          {i.identificador && <span>{i.identificador}</span>}
          <button className={i.favorito ? "text-dourado" : "text-suave"} aria-label={i.favorito ? "Tirar dos favoritos" : "Favoritar"}
            onClick={() => enviar("/conhecimento/favoritos", "POST", { tipo: "biblioteca", ref_id: i.id, favorito: !i.favorito }).then(() => setI({ ...i, favorito: !i.favorito }))}>
            {i.favorito ? "★ Favorito" : "☆ Favoritar"}
          </button>
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {i.alertas.length > 0 && <Aviso tom="alerta"><strong>Atenção:</strong> {i.alertas.join(" · ")}</Aviso>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Cartao titulo={i.versao_atual ? `Texto (versão ${i.versao_atual})` : "Texto"}>
            {i.ementa && <p className="mb-3 text-sm text-suave">{i.ementa}</p>}
            {i.licenca === "referencia" ? <p className="text-sm">Obra protegida cadastrada só como referência. O texto não é copiado para o sistema.</p>
              : i.texto ? <div className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md bg-superficie-2 p-4 font-serif text-sm leading-6" aria-label="Texto conferido">{i.texto}</div>
                : <p className="text-sm text-suave">Ainda não há texto conferido.{i.url_origem ? " Use “Consultar a fonte agora” e confira a versão coletada." : ""}</p>}
            {i.pode_gerenciar && i.licenca !== "referencia" && (
              <div className="mt-3">
                {!novoTexto ? <Botao variante="secundario" onClick={() => setNovoTexto(true)}>Informar texto novo</Botao> : (
                  <form aria-label="Novo texto" className="flex flex-col gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
                    e.preventDefault();
                    const texto = String(new FormData(e.currentTarget).get("texto") ?? "");
                    acao(async () => { await enviar(`/biblioteca/${id}/versoes`, "POST", { texto }); setNovoTexto(false); return recarregar(); }, "Nova versão registrada");
                  }}>
                    <AreaTexto id="bi-texto" name="texto" rotulo="Texto completo" rows={10} required minLength={10} defaultValue={i.texto ?? ""} />
                    <div className="flex gap-2"><Botao type="submit" disabled={ocupado}>Salvar como nova versão</Botao><Botao type="button" variante="secundario" onClick={() => setNovoTexto(false)}>Cancelar</Botao></div>
                  </form>
                )}
              </div>
            )}
          </Cartao>

          <Cartao titulo={`Versões (${i.versoes.length})`}>
            {i.versoes.length === 0 ? <p className="text-sm text-suave">Nenhuma versão ainda.</p> : (
              <ul className="divide-y divide-borda" aria-label="Versões do item">
                {[...i.versoes].reverse().map((v) => (
                  <li key={v.numero} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                    <div>
                      <span className="font-medium">v{v.numero}</span> · {MOTIVO_VERSAO_ITEM[v.motivo] ?? v.motivo} · coletada em {dataHora(v.coletado_em)}
                      {v.url_coleta && <> · <a className="text-dourado underline" href={v.url_coleta} target="_blank" rel="noopener noreferrer">origem</a></>}
                      <p className="text-xs text-suave">{v.situacao === "conferida" ? `Conferida por ${v.conferida_por ?? "—"} em ${dataHora(v.conferida_em)}` : v.situacao === "descartada" ? "Descartada" : "A conferir"} · {v.tamanho.toLocaleString("pt-BR")} caracteres · SHA-256 {v.sha256.slice(0, 12)}…</p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {v.atual && <Selo tom="ok">Atual</Selo>}
                      {v.situacao === "a_conferir" && <Selo tom="alerta">A conferir</Selo>}
                      <Botao variante="secundario" onClick={() => api<{ numero: number; texto: string }>(`/biblioteca/${id}/versoes/${v.numero}`).then(setVerTexto).catch((e) => setErro(e.message))}>Ver</Botao>
                      {i.versao_atual > 0 && v.numero !== i.versao_atual && (
                        <Botao variante="secundario" onClick={() => api<Diff>(`/biblioteca/${id}/comparar?a=${Math.min(v.numero, i.versao_atual)}&b=${Math.max(v.numero, i.versao_atual)}`).then(setCmp).catch((e) => setErro(e.message))}>Comparar com a atual</Botao>
                      )}
                      {v.situacao === "a_conferir" && i.pode_conferir && <>
                        <Botao disabled={ocupado} onClick={() => acao(() => enviar(`/biblioteca/${id}/versoes/${v.numero}/conferir`, "POST", { aceitar: true }), `Versão ${v.numero} conferida`)}>Conferir e usar</Botao>
                        <Botao variante="perigo" disabled={ocupado} onClick={() => {
                          const obs = window.prompt("Por que descartar esta versão?");
                          if (obs) acao(() => enviar(`/biblioteca/${id}/versoes/${v.numero}/conferir`, "POST", { aceitar: false, observacao: obs }), "Versão descartada");
                        }}>Descartar</Botao>
                      </>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {verTexto && (
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between"><strong className="text-sm">Texto da v{verTexto.numero}</strong><button className="text-sm text-dourado underline" onClick={() => setVerTexto(null)}>Fechar</button></div>
                <div className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-superficie-2 p-3 font-serif text-sm" aria-label={`Texto da versão ${verTexto.numero}`}>{verTexto.texto}</div>
              </div>
            )}
            {cmp && (
              <div className="mt-3">
                <div className="mb-1 flex items-center justify-between"><strong className="text-sm">Diferenças entre v{cmp.a} e v{cmp.b}</strong><button className="text-sm text-dourado underline" onClick={() => setCmp(null)}>Fechar</button></div>
                {cmp.iguais ? <p className="text-sm">Os textos são iguais.</p> : (
                  <pre className="max-h-96 overflow-auto rounded-md bg-superficie-2 p-3 text-xs" aria-label="Diferenças">
                    {cmp.diferencas.map((ln, k) => <div key={k} className={ln.startsWith("+") && !ln.startsWith("+++") ? "text-ok" : ln.startsWith("-") && !ln.startsWith("---") ? "text-perigo line-through" : "text-suave"}>{ln}</div>)}
                  </pre>
                )}
              </div>
            )}
          </Cartao>
        </div>

        <div className="flex flex-col gap-4">
          <Cartao titulo="Origem e monitoramento">
            <dl className="grid gap-2 text-sm">
              <div><dt className="text-suave">Fonte</dt><dd>{i.fonte ? `${i.fonte.nome}${i.fonte.oficial ? " (oficial)" : ""}` : "—"}</dd></div>
              <div><dt className="text-suave">Endereço</dt><dd className="break-all">{i.url_origem ? <a className="text-dourado underline" href={i.url_origem} target="_blank" rel="noopener noreferrer">{i.url_origem}</a> : "—"}</dd></div>
              <div><dt className="text-suave">Monitorado</dt><dd>{i.monitorar ? "Sim, uma consulta por dia" : "Não"}</dd></div>
              <div><dt className="text-suave">Última consulta</dt><dd>{dataHora(i.verificado_em)}{i.erro_verificacao ? ` — falhou: ${i.erro_verificacao}` : ""}</dd></div>
              <div><dt className="text-suave">Texto atual coletado em</dt><dd>{dataHora(i.coletado_em)}</dd></div>
            </dl>
            {i.pode_gerenciar && i.url_origem && i.situacao !== "arquivado" && (
              <div className="mt-3"><Botao variante="secundario" disabled={ocupado} onClick={() => acao(() => enviar(`/biblioteca/${id}/verificar`, "POST"), "")}>Consultar a fonte agora</Botao></div>
            )}
          </Cartao>

          <Cartao titulo="Vigência">
            <p className="text-sm">{i.vigencia_rotulo}{i.vigencia_desde ? ` desde ${new Date(i.vigencia_desde + "T12:00").toLocaleDateString("pt-BR")}` : ""}{i.vigencia_ate ? ` até ${new Date(i.vigencia_ate + "T12:00").toLocaleDateString("pt-BR")}` : ""}</p>
            <p className="text-xs text-suave">{i.vigencia_conferida_em ? `Conferida por ${i.vigencia_conferida_por ?? "—"} em ${dataHora(i.vigencia_conferida_em)}` : "Ainda não conferida por advogado."}</p>
            {i.pode_conferir && i.situacao !== "arquivado" && (
              <form aria-label="Conferir vigência" className="mt-3 grid gap-2" onSubmit={(e: FormEvent<HTMLFormElement>) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                acao(() => enviar(`/biblioteca/${id}/vigencia`, "POST", { vigencia: f.get("vigencia"), desde: f.get("desde") || null, ate: f.get("ate") || null, observacao: String(f.get("observacao") ?? "").trim() || null }), "Vigência conferida");
              }}>
                <Selecao id="vg-vigencia" name="vigencia" rotulo="Vigência conferida" defaultValue={i.vigencia === "a_conferir" ? "vigente" : i.vigencia}>
                  <option value="vigente">Vigente</option><option value="parcialmente_revogado">Parcialmente revogado</option>
                  <option value="revogado">Revogado</option><option value="nao_se_aplica">Não se aplica</option>
                </Selecao>
                <div className="grid grid-cols-2 gap-2">
                  <Campo id="vg-desde" name="desde" type="date" rotulo="Desde" />
                  <Campo id="vg-ate" name="ate" type="date" rotulo="Até" />
                </div>
                <Campo id="vg-obs" name="observacao" rotulo="Observação (norma revogadora, dispositivo)" maxLength={1000} />
                <Botao type="submit" disabled={ocupado}>Registrar vigência</Botao>
              </form>
            )}
          </Cartao>

          {i.pode_gerenciar && colecoes.length > 0 && (
            <Cartao titulo="Coleções">
              <ul className="flex flex-col gap-1 text-sm">
                {colecoes.map((c) => {
                  const dentro = i.colecoes.includes(c.id);
                  return (
                    <li key={c.id}><label className="flex items-center gap-2"><input type="checkbox" checked={dentro} onChange={() =>
                      enviar(`/conhecimento/colecoes/${c.id}/itens`, "POST", { tipo: "biblioteca", ref_id: i.id, incluir: !dentro })
                        .then(() => setI({ ...i, colecoes: dentro ? i.colecoes.filter((x) => x !== c.id) : [...i.colecoes, c.id] })).catch((e) => setErro(e.message))} /> {c.nome}</label></li>
                  );
                })}
              </ul>
            </Cartao>
          )}

          {i.pode_gerenciar && (
            <Cartao titulo="Arquivo">
              {i.situacao === "arquivado" ? <Botao variante="secundario" onClick={() => acao(() => enviar(`/biblioteca/${id}/desarquivar`, "POST"), "Item desarquivado")}>Desarquivar</Botao>
                : <Botao variante="perigo" onClick={() => { const m = window.prompt("Motivo do arquivamento"); if (m) acao(() => enviar(`/biblioteca/${id}/arquivar`, "POST", { motivo: m }), "Item arquivado"); }}>Arquivar</Botao>}
            </Cartao>
          )}
        </div>
      </div>
    </div>
  );
}
