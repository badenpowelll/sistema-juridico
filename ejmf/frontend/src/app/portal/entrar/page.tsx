"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Aviso, Botao, Campo, Cartao } from "@/componentes/ui";
import { enviar } from "@/lib/api";

export default function EntrarPortal() {
  const router = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  async function entrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null); setOcupado(true);
    try { await enviar("/portal/entrar", "POST", { email: f.get("email"), senha: f.get("senha") }); router.push("/portal"); }
    catch (x) { setErro((x as Error).message); } finally { setOcupado(false); }
  }
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Portal do cliente</h1>
      <p className="text-sm text-suave">Acompanhe seus processos, envie documentos e fale com o escritório.</p>
      <Cartao>
        <form onSubmit={entrar} className="flex flex-col gap-4" aria-label="Entrar no portal">
          {erro && <Aviso>{erro}</Aviso>}
          <Campo id="pe-email" name="email" type="email" rotulo="E-mail" autoComplete="username" required />
          <Campo id="pe-senha" name="senha" type="password" rotulo="Senha" autoComplete="current-password" required />
          <Botao type="submit" disabled={ocupado}>{ocupado ? "Entrando…" : "Entrar"}</Botao>
        </form>
      </Cartao>
      <p className="text-xs text-suave">Ainda não tem acesso? Peça o convite ao escritório. Esqueceu a senha? O escritório gera um novo convite. A equipe do escritório entra por <Link href="/entrar" className="underline">outra página</Link>.</p>
    </div>
  );
}
