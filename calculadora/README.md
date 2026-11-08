# Sistema Jurídico

## Estrutura
- `src/core/tabelas.js`: tabelas oficiais (INSS 2026, IRRF 2026 com a redução da Lei 15.270, salário-família), mais funções de INSS, IRRF e datas. Todos os módulos usam este arquivo.
- `src/modulos/rescisao/motor.js`: cálculo da rescisão, sem nenhuma parte de tela. Recebe os dados e devolve as verbas com memória de cálculo e fundamento legal.
- `src/core/arquivos.js`: salvar arquivos (downloads no claude.ai ou download direto) e ler datas e valores de planilhas.
- `src/modulos/rescisao/ui.js`: a tela do módulo.
- `src/modulos/rescisao/pdf.js`: o termo em PDF (jsPDF + autotable), com um ou vários trabalhadores.
- `src/modulos/rescisao/lote.js`: importação de planilha (SheetJS). Acha o cabeçalho sozinho, reconhece as colunas e exporta PDF único, ZIP com um PDF por pessoa (JSZip) ou planilha consolidada.
- `src/index.html`: a página. As linhas `<!--INLINE:...-->` marcam onde os scripts são embutidos.
- `build.py`: gera `dist/calculadora-rescisao.html`, que funciona sozinho: é só abrir no navegador e imprimir.

Para criar um módulo novo (férias, horas extras...), crie `src/modulos/<nome>/motor.js` e `ui.js` e reaproveite o `core`.

## Regras adotadas
- Aviso proporcional: 30 dias + 3 por ano completo, com máximo de 90 (Lei 12.506/11 e Nota Técnica MTE 184/2012). O aviso indenizado projeta o contrato para o 13º e as férias (OJ 82 SDI-1).
- 13º e férias: conta 1/12 a fração de 15 dias ou mais. As faltas reduzem os dias de férias conforme o art. 130. As férias entram em dobro quando o período concessivo já venceu (art. 137).
- INSS: não incide sobre aviso indenizado por padrão (há opção para incluir), nem sobre férias indenizadas e indenizações.
- IRRF: saldo de salário com dedução legal ou desconto simplificado, o que for mais vantajoso. O 13º tem tributação exclusiva. A redução de 2026 vale para os dois.
- Culpa recíproca: 50% do aviso, do 13º e das férias proporcionais, e multa de 20%. Acordo (art. 484-A): 50% do aviso e multa de 20%.
