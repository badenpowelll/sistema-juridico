# Sistema Jurídico — instruções para o Claude Code

Leia `docs/ARQUITETURA.md` e `docs/PLANO.md` antes de qualquer mudança. A especificação original do escritório está em `docs/especificacao-original.md`.

- Idioma do código, da interface e dos commits: português.
- Painel exclusivo de advogados. O associado só acessa `/f/<token>`, e toda autorização do formulário é feita no servidor pelo token.
- Nunca versionar segredos, `.env`, planilhas ou PDFs com dados de trabalhadores.
- Cálculos: motor determinístico e testado. Ao mudar tabelas (INSS, IRRF), criar nova `versao_regras`; não alterar a versão antiga.
- IA: só para minutas, só com informações fornecidas. Nunca inventar fatos, valores, datas, provas ou jurisprudência. Marcar lacunas com `[CONFIRMAR]`.
- Consultas de CNPJ/CEP que não retornarem deixam o campo vazio e editável.
- Trabalhar por etapas do `docs/PLANO.md`, com testes antes de avançar.
- `calculadora/` é a calculadora atual em produção (HTML autocontido). Não quebrar; gerar com `python3 calculadora/build.py`.
