# ADR-0002 — Núcleo próprio em vez de plataforma pronta

- Status: aceito · Data: 2026-11-24

## Contexto
A pesquisa (RESEARCH.md) mostrou que nenhum projeto público cobre o escopo. Os jurídicos brasileiros são pequenos (0–8★) e alguns sem licença. As plataformas grandes (Dify, ERPNext, Twenty, Chatwoot) duplicariam o núcleo, trazem licenças copyleft/fair-code e custo de operação alto para um advogado solo.

## Decisão
Monólito modular próprio. Componentes externos entram só como **biblioteca permissiva** (LangGraph, SDK LiteLLM, Tesseract, trechos do pydatajud) ou como **serviço separado e opcional, falando por API** (Documenso, n8n, Metabase, Uptime Kuma).

## Consequências
Mais código próprio, mas um único banco, um único modelo de permissões e auditoria em tudo. Nenhuma licença copyleft contamina o núcleo.
