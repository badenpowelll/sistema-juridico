"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Aviso, Botao, Campo, Cartao } from "@/componentes/ui";
import { enviar } from "@/lib/api";

export default function AtivarPortal() {
  const { token } = useParams<{ token: string }>();
  const [erro, setErro] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  async function ativar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const senha = String(f.get("senha") ?? "");
    setErro(null);
    if (senha !== f.get("repetir")) { setErro("As senhas não conferem."); return; }
    try { const r = await enviar<{ email: string }>("/portal/ativar", "POST", { token, senha }); setEmail(r.email); }
    catch (x) { setErro((x as Error).message); }
  }
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Criar acesso ao portal</h1>
      {email ? (
        <Cartao>
          <Aviso tom="ok">Acesso criado para {email}.</Aviso>
          <p className="mt-3 text-sm"><Link href="/portal/entrar" className="text-dourado hover:underline">Entrar no portal</Link></p>
        </Cartao>
      ) : (
        <Cartao>
          <form onSubmit={ativar} className="flex flex-col gap-4" aria-label="Criar senha">
            {erro && <Aviso>{erro}</Aviso>}
            <Campo id="pa-senha" name="senha" type="password" rotulo="Crie uma senha" ajuda="Pelo menos 12 caracteres. Uma frase fácil de lembrar funciona bem." autoComplete="new-password" required minLength={12} />
            <Campo id="pa-repetir" name="repetir" type="password" rotulo="Repita a senha" autoComplete="new-password" required minLength={12} />
            <Botao type="submit">Criar acesso</Botao>
          </form>
        </Cartao>
      )}
      <p className="text-xs text-suave">O convite vale uma única vez. Se ele expirou, peça outro ao escritório.</p>
    </div>
  );
}
