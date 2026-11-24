"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { enviarArquivoCom, tamanho } from "@/lib/atendimento";
import { EXTRACAO, METODO, ORIGEM, SITUACAO_DOC, TIPO_VERSAO, type Comparacao, type DetalheDocumento } from "@/lib/documentos";

export default function DetalheDocumentoPagina() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<DetalheDocumento | null>(null);
  const [cats, setCats] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cmp, setCmp] = useState<Comparacao | null>(null);
  const [verTexto, setVerTexto] = useState(false);

  const carregar = useCallback(() => api<DetalheDocumento>(`/documentos/${id}`).then(setD).catch((e) => setErro(e.message)), [id]);
  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api<Record<string, string>>("/documentos/categorias").then(setCats).catch(() => {}); }, []);

  async function agir(fn: () => Promise<unknown>, sucesso: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(sucesso); await carregar(); } catch (x) { setErro((x as Error).message); }
  }

  function pedirMotivo(pergunta: string): string | null {
    const m = window.prompt(pergunta);
    return m && m.trim().length >= 5 ? m.trim() : null;
  }

  async function novaVersao(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const arquivo = new FormData(e.currentTarget).get("arquivo") as File | null;
    if (!arquivo?.size) return;
    const form = e.currentTarget;
    await agir(() => enviarArquivoCom(`/documentos/${id}/versoes`, arquivo), "Nova versão guardada. O original continua disponível.");
    form.reset();
  }

  async function comparar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try { setCmp(await api<Comparacao>(`/documentos/${id}/comparar?a=${f.get("a")}&b=${f.get("b")}`)); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !d) return <Aviso>{erro}</Aviso>;
  if (!d) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rs, ts] = SITUACAO_DOC[d.situacao] ?? [d.situacao, "neutro"];
  const arquivos = d.versoes.filter((v) => v.tem_arquivo);
  const pendente = d.versoes.some((v) => v.tem_arquivo && v.extracao === "pendente");
  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/documentos" className="text-sm text-dourado hover:underline">← Documentos</Link>
        <h1 className="font-serif text-3xl font-semibold">{d.titulo}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-suave">
          <Selo tom={ts}>{rs}</Selo>
          <Selo tom="info">{d.categoria_rotulo ?? d.categoria}</Selo>
          {d.categoria_por === "regra" && <span className="text-xs">classificado automaticamente</span>}
          {d.sigiloso && <Selo tom="perigo">Sigiloso</Selo>}
          <span>{ORIGEM[d.origem] ?? d.origem} · {dataHora(d.criado_em)}</span>
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {d.situacao === "quarentena" && (
        <Aviso>Em quarentena: {d.motivo_situacao}. O arquivo não é aberto, processado nem baixado até ser liberado por quem tem acesso a documentos sigilosos.</Aviso>
      )}
      {d.situacao === "arquivado" && d.motivo_situacao && <Aviso tom="neutro">Arquivado: {d.motivo_situacao}</Aviso>}

      <div className="grid gap-5 lg:grid-cols-3">
        <Cartao titulo="Dados" className="lg:col-span-1">
          <dl className="flex flex-col gap-3 text-sm">
            <div><dt className="text-xs text-suave">Cliente</dt><dd>{d.cliente_id ? <Link className="text-dourado hover:underline" href={`/painel/clientes/${d.cliente_id}`}>{d.cliente_nome}</Link> : "—"}</dd></div>
            <div><dt className="text-xs text-suave">Processo</dt><dd>{d.processo_id ? <Link className="font-mono text-xs text-dourado hover:underline" href={`/painel/processos/${d.processo_id}`}>{d.processo_numero}</Link> : "—"}</dd></div>
            {d.atendimento_id && <div><dt className="text-xs text-suave">Atendimento</dt><dd><Link className="text-dourado hover:underline" href={`/painel/atendimentos/${d.atendimento_id}`}>Abrir atendimento</Link></dd></div>}
            {d.minuta_id && <div><dt className="text-xs text-suave">Minuta de origem</dt><dd><Link className="text-dourado hover:underline" href={`/painel/minutas/${d.minuta_id}`}>Abrir minuta</Link></dd></div>}
            <div><dt className="text-xs text-suave">SHA-256 do original</dt><dd className="break-all font-mono text-xs">{d.sha256}</dd></div>
          </dl>
          {d.pode_gerenciar && d.situacao === "ativo" && (
            <form className="mt-4 flex flex-col gap-3 border-t border-borda pt-4" aria-label="Alterar documento"
              onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget);
                agir(() => enviar(`/documentos/${id}`, "PATCH", { titulo: String(f.get("titulo")).trim(), categoria: f.get("categoria") }), "Alterações salvas."); }}>
              <Campo id="dd-titulo" name="titulo" rotulo="Título" defaultValue={d.titulo} required minLength={2} />
              <Selecao id="dd-cat" name="categoria" rotulo="Categoria" defaultValue={d.categoria}>
                {Object.entries(cats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Selecao>
              <Botao type="submit" variante="secundario">Salvar</Botao>
            </form>
          )}
          <div className="mt-4 flex flex-wrap gap-2 border-t border-borda pt-4">
            {d.pode_gerenciar && pendente && d.situacao !== "quarentena" && (
              <Botao variante="secundario" onClick={() => agir(() => enviar(`/documentos/${id}/processar`, "POST"), "Processamento concluído.")}>Processar agora</Botao>
            )}
            {d.pode_liberar && d.situacao === "quarentena" && (
              <Botao variante="perigo" onClick={() => { const m = pedirMotivo("Explique por que o arquivo é seguro (fica na auditoria):"); if (m) agir(() => enviar(`/documentos/${id}/liberar`, "POST", { motivo: m }), "Arquivo liberado; o texto será extraído."); }}>Liberar da quarentena</Botao>
            )}
            {d.pode_arquivar && d.situacao === "ativo" && (
              <Botao variante="secundario" onClick={() => { const m = pedirMotivo("Motivo do arquivamento:"); if (m) agir(() => enviar(`/documentos/${id}/arquivar`, "POST", { motivo: m }), "Documento arquivado."); }}>Arquivar</Botao>
            )}
            {d.pode_arquivar && d.situacao === "arquivado" && (
              <Botao variante="secundario" onClick={() => agir(() => enviar(`/documentos/${id}/desarquivar`, "POST"), "Documento reativado.")}>Desarquivar</Botao>
            )}
          </div>
        </Cartao>

        <Cartao titulo="Versões" className="lg:col-span-2">
          <ul className="divide-y divide-borda" aria-label="Versões">
            {[...d.versoes].reverse().map((v) => {
              const [re, te] = EXTRACAO[v.extracao] ?? [v.extracao, "neutro"];
              return (
                <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <div>
                    <span className="font-medium">v{v.numero} · {TIPO_VERSAO[v.tipo] ?? v.tipo}</span>
                    {v.derivada_de && <span className="text-xs text-suave"> (de v{v.derivada_de})</span>}
                    <div className="text-xs text-suave">
                      {[v.nome_arquivo, v.tamanho != null ? tamanho(v.tamanho) : null, v.paginas ? `${v.paginas} página(s)` : null,
                        v.metodo ? METODO[v.metodo] ?? v.metodo : null, v.confianca != null ? `confiança ${Math.round(v.confianca)}%` : null,
                        !v.tem_arquivo ? `${v.caracteres.toLocaleString("pt-BR")} caracteres` : null, dataHora(v.criado_em)].filter(Boolean).join(" · ")}
                    </div>
                    {v.erro && <div className="text-xs text-alerta">{v.erro}</div>}
                  </div>
                  <div className="flex items-center gap-2">
                    {v.tem_arquivo && <Selo tom={te}>{re}</Selo>}
                    {(d.situacao !== "quarentena" || d.pode_liberar) && (
                      <a className="text-xs text-dourado hover:underline" href={`/api/v1/documentos/${id}/versoes/${v.numero}/arquivo`}>Baixar</a>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          {d.pode_gerenciar && d.situacao === "ativo" && (
            <form onSubmit={novaVersao} className="mt-4 flex flex-wrap items-end gap-3 border-t border-borda pt-4" aria-label="Nova versão">
              <div className="flex flex-col gap-1"><label htmlFor="dv-arquivo" className="text-sm font-medium">Nova versão do arquivo</label>
                <input id="dv-arquivo" name="arquivo" type="file" required className="text-sm" /></div>
              <Botao type="submit" variante="secundario">Guardar nova versão</Botao>
            </form>
          )}
          {arquivos.length > 1 && (
            <form onSubmit={comparar} className="mt-4 flex flex-wrap items-end gap-3 border-t border-borda pt-4" aria-label="Comparar versões">
              <Selecao id="dc-a" name="a" rotulo="Comparar" defaultValue={String(arquivos[0].numero)}>
                {arquivos.map((v) => <option key={v.numero} value={v.numero}>v{v.numero}</option>)}
              </Selecao>
              <Selecao id="dc-b" name="b" rotulo="com" defaultValue={String(arquivos[arquivos.length - 1].numero)}>
                {arquivos.map((v) => <option key={v.numero} value={v.numero}>v{v.numero}</option>)}
              </Selecao>
              <Botao type="submit" variante="secundario">Comparar</Botao>
            </form>
          )}
          {cmp && (
            <div className="mt-4 rounded-md border border-borda p-3 text-sm" aria-label="Diferenças">
              <p className="mb-2 font-medium">v{cmp.a} → v{cmp.b}: {cmp.iguais ? "o texto é igual" : "diferenças encontradas"}</p>
              {cmp.blocos.map((b, i) => (
                <div key={i} className={b.tipo === "incluido" ? "bg-ok/10 text-ok" : b.tipo === "removido" ? "bg-perigo/10 text-perigo line-through" : "text-suave"}>
                  {b.linhas.map((ln, j) => <div key={j} className="whitespace-pre-wrap font-mono text-xs">{b.tipo === "incluido" ? "+ " : b.tipo === "removido" ? "− " : "  "}{ln}</div>)}
                </div>
              ))}
            </div>
          )}
        </Cartao>
      </div>

      <Cartao titulo="Texto extraído" acao={d.texto ? <button className="text-sm text-dourado hover:underline" onClick={() => setVerTexto((v) => !v)}>{verTexto ? "Ocultar" : "Mostrar"}</button> : undefined}>
        {!d.texto ? <p className="text-sm text-suave">{pendente ? "Aguardando o processamento." : "Nenhum texto extraído deste arquivo."}</p>
          : verTexto ? <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded bg-superficie-2 p-3 text-xs" aria-label="Conteúdo extraído">{d.texto}</pre>
            : <p className="text-sm text-suave">{d.texto.length.toLocaleString("pt-BR")} caracteres{d.texto_cortado && " (mostrando o início)"}. O texto do OCR pode conter erros de leitura: confira no original.</p>}
      </Cartao>
    </div>
  );
}
