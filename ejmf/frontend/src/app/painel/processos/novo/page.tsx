"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { Aviso, AreaTexto, Botao, Campo, Cartao, Selecao } from "@/componentes/ui";
import { api, enviar, ErroApi } from "@/lib/api";
import { POLO, STATUS_PROCESSO } from "@/lib/rotulos";
import type { Cliente, Departamento, Prontuario } from "@/lib/tipos";

export default function NovoProcesso() {
  const router = useRouter();
  const [deps, setDeps] = useState<Departamento[]>([]);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [existente, setExistente] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { api<Departamento[]>("/departamentos").then((d) => setDeps(d.filter((x) => x.ativo))).catch(() => {}); }, []);

  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const txt = (k: string) => (String(f.get(k) ?? "").trim() || null);
    const partes = [];
    if (cliente) partes.push({ nome: cliente.nome, polo: f.get("polo_cliente"), cliente_id: cliente.id });
    if (txt("parte_contraria")) partes.push({ nome: txt("parte_contraria"), polo: f.get("polo_cliente") === "ativo" ? "passivo" : "ativo" });
    setErro(null); setExistente(null); setEnviando(true);
    try {
      const p = await enviar<Prontuario>("/processos", "POST", {
        numero: txt("numero"), classe: txt("classe"), unidade: txt("unidade"), status: f.get("status"),
        departamento_id: txt("departamento_id"), valor_causa: txt("valor_causa")?.replace(/\./g, "").replace(",", ".") ?? null,
        data_distribuicao: txt("data_distribuicao"), observacoes: txt("observacoes"),
        assuntos: (txt("assuntos") ?? "").split(";").map((a) => a.trim()).filter(Boolean), partes,
      });
      router.push(`/painel/processos/${p.id}`);
    } catch (x) {
      if (x instanceof ErroApi && x.status === 409) setExistente("Este número já está cadastrado.");
      setErro((x as Error).message);
      setEnviando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div><Link href="/painel/processos" className="text-sm text-dourado hover:underline">← Processos</Link>
        <h1 className="font-serif text-3xl font-semibold">Novo processo</h1></div>
      {erro && <Aviso>{existente ?? erro}</Aviso>}
      <form onSubmit={salvar} className="flex flex-col gap-4">
        <Cartao titulo="Identificação">
          <div className="grid gap-4 md:grid-cols-2">
            <Campo id="numero" name="numero" rotulo="Número único (CNJ)" required placeholder="0000000-00.0000.0.00.0000"
              ajuda="O tribunal é identificado pelo próprio número. O dígito verificador é conferido." inputMode="numeric" />
            <Campo id="classe" name="classe" rotulo="Classe" placeholder="Ex.: Ação Trabalhista - Rito Ordinário" />
            <Campo id="unidade" name="unidade" rotulo="Unidade / órgão julgador" placeholder="Ex.: 1ª Vara do Trabalho de Natal" />
            <Campo id="assuntos" name="assuntos" rotulo="Assuntos" ajuda="Separe por ponto e vírgula." />
            <Selecao id="status" name="status" rotulo="Situação" defaultValue="ativo">
              {Object.entries(STATUS_PROCESSO).map(([v, [r]]) => <option key={v} value={v}>{r}</option>)}
            </Selecao>
            <Selecao id="departamento_id" name="departamento_id" rotulo="Departamento" defaultValue="">
              <option value="">Não definido</option>
              {deps.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
            </Selecao>
            <Campo id="valor_causa" name="valor_causa" rotulo="Valor da causa (R$)" inputMode="decimal" placeholder="0,00" />
            <Campo id="data_distribuicao" name="data_distribuicao" rotulo="Data de distribuição" type="date" />
          </div>
        </Cartao>
        <Cartao titulo="Partes">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2"><BuscaCliente id="cliente" rotulo="Cliente do escritório (opcional)" aoEscolher={setCliente} /></div>
            <Selecao id="polo_cliente" name="polo_cliente" rotulo="Polo do cliente" defaultValue="ativo">
              <option value="ativo">{POLO.ativo}</option><option value="passivo">{POLO.passivo}</option>
            </Selecao>
            <div className="md:col-span-3"><Campo id="parte_contraria" name="parte_contraria" rotulo="Parte contrária (opcional)" /></div>
          </div>
          <p className="mt-3 text-xs text-suave">O cliente precisa estar cadastrado. <Link href="/painel/clientes" className="text-dourado hover:underline">Cadastrar cliente</Link></p>
        </Cartao>
        <Cartao><AreaTexto id="observacoes" name="observacoes" rotulo="Observações" /></Cartao>
        <div className="flex justify-end gap-2">
          <Link href="/painel/processos" className="rounded-md border border-borda px-4 py-2 text-sm">Cancelar</Link>
          <Botao type="submit" disabled={enviando}>{enviando ? "Salvando…" : "Cadastrar processo"}</Botao>
        </div>
      </form>
    </div>
  );
}
