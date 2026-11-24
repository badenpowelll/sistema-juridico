/**
 * Módulo central da marca do Escritório Jurídico Márcio Fernandes.
 * Toda tela, documento, e-mail e notificação deve ler a identidade daqui.
 * Dados institucionais não fornecidos (CNPJ, endereço, telefone, e-mail) NÃO ficam aqui:
 * vêm das configurações do sistema (/api/v1/marca) e só aparecem quando preenchidos.
 */
export const marca = {
  nome: "Escritório Jurídico Márcio Fernandes",
  nomeCurto: "Márcio Fernandes",
  sigla: "EJMF",
  slogan: "Advocacia, Tecnologia e Inteligência",
  responsavel: "Dr. Márcio Oliveira Fernandes",
  oab: "OAB/RN 12.114",
  idioma: "pt-BR",
  fuso: "America/Fortaleza",
  // Paleta institucional (as variáveis CSS ficam em ./tema.css, nos modos claro e escuro)
  cores: {
    marinho: "#0B1F3A",
    marinhoProfundo: "#071428",
    dourado: "#B8955A",
    douradoClaro: "#D6BC8A",
    branco: "#FFFFFF",
    cinza: "#5B6472",
    cinzaClaro: "#EEF0F3",
  },
} as const;

export type Marca = typeof marca;
