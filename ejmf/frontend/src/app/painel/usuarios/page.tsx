"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";

type Usuario = { id: string; email: string; nome: string; ativo: boolean; mfa_ativo: boolean; perfis: string[]; ultimo_login_em: string | null };
type Perfil = { codigo: string; nome: string };

export default function Usuarios() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("usuarios:gerenciar");
  const [lista, setLista] = useState<Usuario[]>([]);
  const [perfis, setPerfis] = useState<Perfil[]>([]);
  const [msg, setMsg] = useState<{ tom: string; texto: string } | null>(null);
  const [provisoria, setProvisoria] = useState<{ nome: string; senha: string; aviso: string } | null>(null);
  const carregar = () => api<Usuario[]>("/usuarios").then(setLista).catch((e) => setMsg({ tom: "perigo", texto: e.message }));
  useEffect(() => { carregar(); api<Perfil[]>("/perfis").then(setPerfis).catch(() => {}); }, []);

  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget; const f = new FormData(form);
    try {
      await enviar("/usuarios", "POST", { nome: f.get("nome"), email: f.get("email"), senha: f.get("senha"), perfis: [f.get("perfil")] });
      form.reset(); setMsg({ tom: "ok", texto: "Usuário criado." }); carregar();
    } catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }
  async function alternar(u: Usuario) {
    try { await enviar(`/usuarios/${u.id}`, "PATCH", { ativo: !u.ativo }); carregar(); } catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }
  async function redefinir(u: Usuario) {
    setMsg(null); setProvisoria(null);
    const zerar = u.mfa_ativo && window.confirm(`Desligar também a verificação em duas etapas de ${u.nome}? Use só se a pessoa perdeu o celular.`);
    try {
      const r = await enviar<{ senha_provisoria: string; aviso: string }>(`/usuarios/${u.id}/redefinir-acesso`, "POST", { zerar_mfa: zerar });
      setProvisoria({ nome: u.nome, senha: r.senha_provisoria, aviso: r.aviso }); carregar();
    } catch (x) { setMsg({ tom: "perigo", texto: (x as Error).message }); }
  }
  const nomePerfil = (c: string) => perfis.find((p) => p.codigo === c)?.nome ?? c;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Usuários</h1>
      {msg && <Aviso tom={msg.tom}>{msg.texto}</Aviso>}
      {provisoria && (
        <div role="status" data-senha-provisoria className="rounded-xl border border-alerta/50 bg-alerta/10 px-4 py-3 text-sm">
          <p className="font-semibold">Senha provisória de {provisoria.nome}</p>
          <p className="my-1 font-mono text-base">{provisoria.senha}</p>
          <p className="text-xs">{provisoria.aviso}</p>
        </div>
      )}
      {pode && (
        <Cartao titulo="Novo usuário">
          <form onSubmit={criar} className="grid gap-3 sm:grid-cols-2">
            <Campo id="u-nome" name="nome" rotulo="Nome" required minLength={2} />
            <Campo id="u-email" name="email" type="email" rotulo="E-mail" required />
            <Campo id="u-senha" name="senha" type="password" rotulo="Senha inicial" minLength={12} required ajuda="Mínimo de 12 caracteres." />
            <div className="flex flex-col gap-1"><label htmlFor="u-perfil" className="text-sm font-medium">Perfil</label>
              <select id="u-perfil" name="perfil" className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm">
                {perfis.filter((p) => p.codigo !== "agente_ia").map((p) => <option key={p.codigo} value={p.codigo}>{p.nome}</option>)}
              </select></div>
            <div><Botao type="submit">Criar</Botao></div>
          </form>
        </Cartao>
      )}
      <Cartao>
        <ul className="divide-y divide-borda">
          {lista.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm">
              <div><div className="font-medium">{u.nome} {!u.ativo && <Selo tom="perigo">Inativo</Selo>} {u.mfa_ativo ? <Selo tom="ok">2 etapas</Selo> : <Selo tom="alerta">Sem 2 etapas</Selo>}</div>
                <div className="text-xs text-suave">{u.email} · {u.perfis.map(nomePerfil).join(", ")} · último acesso {dataHora(u.ultimo_login_em)}</div></div>
              {pode && u.id !== eu.id && (
                <div className="flex gap-2">
                  {u.ativo && <Botao variante="secundario" onClick={() => redefinir(u)}>Redefinir acesso</Botao>}
                  <Botao variante="secundario" onClick={() => alternar(u)}>{u.ativo ? "Desativar" : "Reativar"}</Botao>
                </div>
              )}
            </li>
          ))}
        </ul>
      </Cartao>
    </div>
  );
}
