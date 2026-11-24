"use client";
import { useEffect, useRef } from "react";

/**
 * Editor de texto no estilo Word: área editável com barra de formatação. O HTML que sai daqui é sanitizado no servidor
 * (só parágrafos, títulos, listas, citação, negrito, itálico, sublinhado, tachado e alinhamento). Para recomeçar com
 * outro conteúdo, troque a `key` do componente.
 */
export function Editor({ inicial, aoMudar, somenteLeitura = false, rotulo, campos }: {
  inicial: string; aoMudar?: (html: string) => void; somenteLeitura?: boolean; rotulo: string;
  campos?: { campo: string; rotulo: string }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.innerHTML = inicial;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function cmd(c: string, valor?: string) {
    ref.current?.focus();
    document.execCommand(c, false, valor);
    if (ref.current) aoMudar?.(ref.current.innerHTML);
  }

  const botoes: [string, string, string, string?][] = [
    ["N", "Negrito", "bold"], ["I", "Itálico", "italic"], ["S", "Sublinhado", "underline"], ["T̶", "Tachado", "strikeThrough"],
    ["¶", "Parágrafo", "formatBlock", "<p>"], ["T1", "Título", "formatBlock", "<h2>"], ["T2", "Subtítulo", "formatBlock", "<h3>"],
    ["❝", "Citação recuada", "formatBlock", "<blockquote>"], ["•", "Lista", "insertUnorderedList"],
    ["1.", "Lista numerada", "insertOrderedList"], ["⇤", "Alinhar à esquerda", "justifyLeft"], ["↔", "Centralizar", "justifyCenter"],
    ["⇥", "Alinhar à direita", "justifyRight"], ["☰", "Justificar", "justifyFull"], ["↶", "Desfazer", "undo"], ["↷", "Refazer", "redo"],
  ];

  return (
    <div className="flex flex-col gap-2">
      {!somenteLeitura && (
        <div role="toolbar" aria-label="Formatação" className="sticky top-0 z-10 flex flex-wrap items-center gap-1 rounded-md border border-borda bg-superficie-2 p-1">
          {botoes.map(([txt, nome, c, v]) => (
            <button key={nome} type="button" title={nome} aria-label={nome} onMouseDown={(e) => e.preventDefault()} onClick={() => cmd(c, v)}
              className="min-w-8 rounded px-2 py-1 text-sm hover:bg-superficie">{txt}</button>
          ))}
          {campos && campos.length > 0 && (
            <select aria-label="Inserir campo" className="ml-auto rounded border border-borda bg-superficie px-2 py-1 text-sm" value=""
              onChange={(e) => { if (e.target.value) cmd("insertText", `{{${e.target.value}}}`); }}>
              <option value="">Inserir campo…</option>
              {campos.map((c) => <option key={c.campo} value={c.campo}>{c.rotulo}</option>)}
            </select>
          )}
        </div>
      )}
      <div className="overflow-x-auto rounded-md bg-superficie-2 p-2 sm:p-6">
        <div ref={ref} role="textbox" aria-multiline="true" aria-label={rotulo} contentEditable={!somenteLeitura} suppressContentEditableWarning
          onInput={(e) => aoMudar?.((e.target as HTMLDivElement).innerHTML)}
          className="folha mx-auto min-h-[60vh] max-w-[21cm] bg-white px-6 py-8 font-serif text-[15px] leading-7 text-black shadow sm:px-[2cm] sm:py-[2.5cm]" />
      </div>
    </div>
  );
}
