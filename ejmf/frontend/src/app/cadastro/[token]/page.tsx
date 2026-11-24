"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar, ErroApi } from "@/lib/api";
import { enviarArquivoCom, type CampoFormulario, type Formulario } from "@/lib/atendimento";

type Valor = string | number | null;
type ItemCrono = { data: string | null; descricao: string; documento_id?: string | null };
type DocLink = { id: string; nome: string; previsto: string | null; situacao: string; motivo: string | null; enviado_em: string };
type Estado = {
  escritorio: string; protocolo: string; finalidade: "cadastro" | "documentos"; expira_em: string; formulario: Formulario;
  dados: Record<string, Valor>; relato: string; cronologia: ItemCrono[]; entrevista: Record<string, string>; passo: number;
  confirmado_em: string | null; pendencias: { campos: string[]; documentos: string[]; relato: boolean };
  documentos: DocLink[]; aviso: string; erros?: Record<string, string>;
};

const SECOES: [string, string][] = [["pessoais", "Seus dados"], ["contato", "Endereço e contato"], ["complementares", "Sobre o caso"]];

export default function CadastroPublico() {
  const { token } = useParams<{ token: string }>();
  const [estado, setEstado] = useState<Estado | null>(null);
  const [falha, setFalha] = useState<{ status: number; msg: string } | null>(null);
  useEffect(() => {
    api<Estado>(`/publico/cadastro/${encodeURIComponent(token)}`).then(setEstado)
      .catch((e) => setFalha({ status: e instanceof ErroApi ? e.status : 0, msg: e.message }));
  }, [token]);

  if (falha) return (
    <Cartao titulo={falha.status === 410 ? "Link indisponível" : falha.status === 404 ? "Link não encontrado" : "Não foi possível abrir"}>
      <p className="text-sm">{falha.status === 404 ? "Confira se o endereço foi copiado inteiro." : falha.msg}</p>
      <p className="mt-2 text-sm text-suave">Se precisar, peça um novo link ao escritório.</p>
    </Cartao>
  );
  if (!estado) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  return <Assistente token={token} inicial={estado} />;
}

function Assistente({ token, inicial }: { token: string; inicial: Estado }) {
  const form = inicial.formulario;
  const so_documentos = inicial.finalidade === "documentos";
  const secoes = SECOES.filter(([s]) => form.campos.some((c) => (c.secao ?? "pessoais") === s));
  const passos = so_documentos ? ["Documentos"] : [...secoes.map(([, r]) => r), "Seu relato", "Linha do tempo", "Documentos", "Revisão"];
  const [estado, setEstado] = useState(inicial);
  const [passo, setPasso] = useState(so_documentos || inicial.confirmado_em ? passos.length - 1 : Math.min(inicial.passo, passos.length - 1));
  const [dados, setDados] = useState<Record<string, Valor>>(inicial.dados);
  const [relato, setRelato] = useState(inicial.relato ?? "");
  const [entrevista, setEntrevista] = useState<Record<string, string>>(inicial.entrevista ?? {});
  const [crono, setCrono] = useState<ItemCrono[]>(inicial.cronologia ?? []);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const confirmado = !!estado.confirmado_em;

  async function salvar(proximo: number) {
    setErro(null); setOk(null); setOcupado(true);
    try {
      const r = await enviar<Estado>(`/publico/cadastro/${encodeURIComponent(token)}`, "PUT", {
        dados, relato, entrevista, cronologia: crono.filter((i) => i.descricao.trim()), passo: proximo,
      });
      setEstado(r);
      const e = r.erros ?? {};
      setErros(e);
      const campoDoPasso = form.campos.filter((c) => secoes[passo]?.[0] === (c.secao ?? "pessoais")).map((c) => c.id);
      if (Object.keys(e).some((k) => campoDoPasso.includes(k) || k === "cronologia" || k === "relato") && proximo > passo) {
        setErro("Confira os campos destacados.");
      } else { setPasso(proximo); setOk("Salvo."); window.scrollTo({ top: 0 }); }
    } catch (x) { setErro((x as Error).message); } finally { setOcupado(false); }
  }

  async function confirmar() {
    setErro(null); setOcupado(true);
    try { setEstado(await enviar<Estado>(`/publico/cadastro/${encodeURIComponent(token)}/confirmar`, "POST")); window.scrollTo({ top: 0 }); }
    catch (x) { setErro((x as Error).message); } finally { setOcupado(false); }
  }

  const nomePasso = passos[passo];
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-sm text-suave">{estado.escritorio} · protocolo <span className="font-mono">{estado.protocolo}</span></p>
        <h1 className="font-serif text-3xl font-semibold">{so_documentos ? "Envio de documentos" : form.titulo}</h1>
        <p className="mt-1 text-xs text-suave">Este link vale até {dataHora(estado.expira_em)}.</p>
      </div>
      <Aviso tom="info">{estado.aviso}</Aviso>
      {confirmado && <Aviso tom="ok">Cadastro enviado ao escritório em {dataHora(estado.confirmado_em)}. Obrigado! Se faltar algum documento, você ainda pode enviá-lo abaixo.</Aviso>}
      {!so_documentos && !confirmado && (
        <ol className="flex flex-wrap gap-2 text-xs" aria-label="Etapas do cadastro">
          {passos.map((p, i) => (
            <li key={p}><button type="button" onClick={() => setPasso(i)} aria-current={i === passo ? "step" : undefined}
              className={`rounded-full border px-3 py-1 ${i === passo ? "border-dourado bg-dourado/10 text-dourado" : "border-borda text-suave"}`}>{i + 1}. {p}</button></li>
          ))}
        </ol>
      )}
      {erro && <Aviso>{erro}</Aviso>}
      {ok && !erro && <Aviso tom="ok">{ok}</Aviso>}

      {!confirmado && secoes[passo] && (
        <Cartao titulo={nomePasso}>
          <div className="grid gap-4 sm:grid-cols-2">
            {form.campos.filter((c) => (c.secao ?? "pessoais") === secoes[passo][0]).map((c) => (
              <CampoDinamico key={c.id} c={c} valor={dados[c.id] ?? null} erro={erros[c.id]} aoMudar={(v) => setDados((d) => ({ ...d, [c.id]: v }))} />
            ))}
          </div>
        </Cartao>
      )}

      {!confirmado && nomePasso === "Seu relato" && (
        <Cartao titulo="Seu relato">
          <div className="flex flex-col gap-4">
            <AreaTexto id="relato" rotulo="Conte com suas palavras o que aconteceu *" value={relato} onChange={(e) => setRelato(e.target.value)} rows={8} maxLength={20000} />
            <p className="-mt-2 text-xs text-suave">Escreva do seu jeito. O texto é guardado exatamente como você escreveu.</p>
            {form.perguntas.filter((p) => p.id !== "o_que_aconteceu").map((p) => (
              <AreaTexto key={p.id} id={`p-${p.id}`} rotulo={p.texto} value={entrevista[p.id] ?? ""} onChange={(e) => setEntrevista((x) => ({ ...x, [p.id]: e.target.value }))} maxLength={8000} />
            ))}
          </div>
        </Cartao>
      )}

      {!confirmado && nomePasso === "Linha do tempo" && (
        <Cartao titulo="Linha do tempo (opcional)">
          <p className="mb-3 text-sm text-suave">Liste os fatos importantes com a data aproximada. Se não lembrar a data, deixe em branco.</p>
          {erros.cronologia && <Aviso>{erros.cronologia}</Aviso>}
          <ul className="flex flex-col gap-3">
            {crono.map((i, n) => (
              <li key={n} className="grid gap-2 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
                <Campo id={`cr-data-${n}`} type="date" rotulo="Data" value={i.data ?? ""} onChange={(e) => setCrono((l) => l.map((x, k) => k === n ? { ...x, data: e.target.value || null } : x))} />
                <Campo id={`cr-desc-${n}`} rotulo="O que aconteceu" value={i.descricao} maxLength={2000} onChange={(e) => setCrono((l) => l.map((x, k) => k === n ? { ...x, descricao: e.target.value } : x))} />
                <Botao type="button" variante="secundario" onClick={() => setCrono((l) => l.filter((_, k) => k !== n))} aria-label={`Remover fato ${n + 1}`}>Remover</Botao>
              </li>
            ))}
          </ul>
          <Botao type="button" variante="secundario" className="mt-3" onClick={() => setCrono((l) => [...l, { data: null, descricao: "" }])} disabled={crono.length >= 60}>Adicionar fato</Botao>
        </Cartao>
      )}

      {nomePasso === "Documentos" && <EnvioDocumentos token={token} estado={estado} aoEnviar={setEstado} />}

      {!confirmado && nomePasso === "Revisão" && <Revisao estado={estado} dados={dados} relato={relato} />}

      {!confirmado && !so_documentos && (
        <div className="flex flex-wrap justify-between gap-2">
          <Botao type="button" variante="secundario" disabled={passo === 0 || ocupado} onClick={() => salvar(passo - 1)}>Voltar</Botao>
          {nomePasso === "Revisão"
            ? <Botao type="button" disabled={ocupado} onClick={confirmar}>Confirmar e enviar ao escritório</Botao>
            : <Botao type="button" disabled={ocupado} onClick={() => salvar(passo + 1)}>{ocupado ? "Salvando…" : "Salvar e continuar"}</Botao>}
        </div>
      )}
    </div>
  );
}

function CampoDinamico({ c, valor, erro, aoMudar }: { c: CampoFormulario; valor: Valor; erro?: string; aoMudar: (v: string) => void }) {
  const id = `c-${c.id}`;
  const rotulo = `${c.rotulo}${c.obrigatorio ? " *" : ""}`;
  const v = valor == null ? "" : String(valor);
  let campo;
  if (c.tipo === "opcao") {
    campo = <Selecao id={id} rotulo={rotulo} value={v} onChange={(e) => aoMudar(e.target.value)}><option value="">Escolha</option>{(c.opcoes ?? []).map((o) => <option key={o} value={o}>{o}</option>)}</Selecao>;
  } else if (c.tipo === "texto_longo") {
    campo = <AreaTexto id={id} rotulo={rotulo} value={v} onChange={(e) => aoMudar(e.target.value)} maxLength={4000} />;
  } else {
    const extra = {
      data: { type: "date" }, cpf: { inputMode: "numeric" as const, autoComplete: "off" }, cep: { inputMode: "numeric" as const, autoComplete: "postal-code" },
      telefone: { type: "tel", autoComplete: "tel" }, email: { type: "email", autoComplete: "email" }, uf: { maxLength: 2 },
    }[c.tipo] ?? {};
    campo = <Campo id={id} rotulo={rotulo} value={v} onChange={(e) => aoMudar(e.target.value)} aria-invalid={erro ? true : undefined} {...extra} />;
  }
  return (
    <div className={c.tipo === "texto_longo" ? "sm:col-span-2" : ""}>
      {campo}
      {erro && <p className="mt-1 text-xs text-perigo" role="alert">{c.rotulo}: {erro}</p>}
    </div>
  );
}

function EnvioDocumentos({ token, estado, aoEnviar }: { token: string; estado: Estado; aoEnviar: (e: Estado) => void }) {
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<string | null>(null);

  async function enviarDoc(previsto: string | null, arquivo: File | undefined) {
    if (!arquivo) return;
    setErro(null); setOk(null); setEnviando(previsto ?? "outro");
    try {
      const r = await enviarArquivoCom<{ duplicado: boolean }>(`/publico/cadastro/${encodeURIComponent(token)}/documentos`, arquivo, { previsto });
      setOk(r.duplicado ? "Este arquivo já tinha sido enviado." : `${arquivo.name} enviado.`);
      aoEnviar(await api<Estado>(`/publico/cadastro/${encodeURIComponent(token)}`));
    } catch (x) { setErro((x as Error).message); } finally { setEnviando(null); }
  }

  const docs = estado.formulario.documentos;
  return (
    <Cartao titulo="Documentos">
      <p className="mb-3 text-sm text-suave">Envie foto nítida ou PDF. Aceitamos PDF, JPG, PNG, HEIC e documentos do Word. Os arquivos ficam guardados com segurança.</p>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      <ul className="flex flex-col divide-y divide-borda">
        {[...docs, { id: "", rotulo: "Outro documento que ajude no caso", obrigatorio: false }].map((d) => {
          const recebidos = estado.documentos.filter((x) => (x.previsto ?? "") === d.id);
          return (
            <li key={d.id || "outro"} className="flex flex-col gap-2 py-3" data-doc-previsto={d.id || "outro"}>
              <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{d.rotulo}</span>
                {d.obrigatorio && <Selo tom="alerta">obrigatório</Selo>}
                {recebidos.some((x) => x.situacao !== "recusado") && <Selo tom="ok">enviado</Selo>}</div>
              {recebidos.map((x) => (
                <p key={x.id} className="text-xs text-suave">{x.nome} · {dataHora(x.enviado_em)}
                  {x.situacao === "recusado" && <span className="text-perigo"> · recusado{x.motivo && `: ${x.motivo}`}. Envie de novo.</span>}
                  {x.situacao === "aceito" && " · conferido"}</p>
              ))}
              <label className="text-sm">
                <span className="sr-only">Arquivo para {d.rotulo}</span>
                <input type="file" aria-label={`Arquivo para ${d.rotulo}`} disabled={!!enviando} className="text-sm"
                  accept=".pdf,.jpg,.jpeg,.png,.heic,.webp,.tif,.tiff,.doc,.docx,.mp3,.ogg,.wav,.m4a,.txt"
                  onChange={(e) => { enviarDoc(d.id || null, e.currentTarget.files?.[0]); e.currentTarget.value = ""; }} />
              </label>
              {enviando === (d.id || "outro") && <p className="text-xs text-suave" aria-live="polite">Enviando…</p>}
            </li>
          );
        })}
      </ul>
    </Cartao>
  );
}

function Revisao({ estado, dados, relato }: { estado: Estado; dados: Record<string, Valor>; relato: string }) {
  const p = estado.pendencias;
  const falta = [...p.campos, ...(p.relato ? ["seu relato"] : [])];
  return (
    <Cartao titulo="Revisão">
      {falta.length > 0 ? <Aviso tom="alerta">Antes de enviar, preencha: {falta.join(", ")}.</Aviso> : <Aviso tom="ok">Tudo pronto para enviar.</Aviso>}
      {p.documentos.length > 0 && <p className="mt-2 text-sm text-suave">Documentos que ainda faltam (pode enviar depois): {p.documentos.join(", ")}.</p>}
      <dl className="mt-4 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
        {estado.formulario.campos.map((c) => (
          <div key={c.id}><dt className="text-xs text-suave">{c.rotulo}</dt><dd>{dados[c.id] == null || dados[c.id] === "" ? <span className="text-suave">—</span> : String(dados[c.id])}</dd></div>
        ))}
      </dl>
      <h3 className="mt-4 text-sm font-semibold">Seu relato</h3>
      {relato.trim() ? <p className="whitespace-pre-wrap text-sm">{relato}</p> : <Vazio>Sem relato.</Vazio>}
      <p className="mt-4 text-xs text-suave">Ao confirmar, o cadastro é enviado e não pode mais ser alterado por este link. Se precisar corrigir algo, fale com o escritório.</p>
    </Cartao>
  );
}
