import type { EngineId } from "../../engineApi";

export type ExtensionLink = { label: string; url: string };

export type ExtensionCatalogEntry = {
  id: EngineId;
  group: "managed-python" | "dynare" | "minsky";
  name: string;
  description: string;
  links: ExtensionLink[];
};

export const ENGINES: ExtensionCatalogEntry[] = [
  {
    id: "mesa",
    group: "managed-python",
    name: "Mesa",
    description: "Motor de simulação baseada em agentes usado no Economy Zero (ativação e componentes Mesa).",
    links: [],
  },
  {
    id: "hark",
    group: "managed-python",
    name: "HARK",
    description: "Biblioteca de política de consumo/poupança em ciclo de vida usada nos módulos de decisão domiciliar.",
    links: [],
  },
  {
    id: "dynare",
    group: "dynare",
    name: "Dynare / Octave",
    description: "Motor de orientação macro (New Keynesian) executado via Octave. Instale o Octave e o Dynare separadamente.",
    links: [
      { label: "Baixar Octave", url: "https://www.gnu.org/software/octave/download.html" },
      { label: "Baixar Dynare", url: "https://www.dynare.org/download/" },
    ],
  },
  {
    id: "minsky",
    group: "minsky",
    name: "Minsky",
    description: "Ponte REST para controles financeiros e reconciliação com o Minsky (Steve Keen). Execute o Minsky com o servidor REST habilitado.",
    links: [
      { label: "Baixar Minsky", url: "https://sourceforge.net/projects/minsky/" },
    ],
  },
];
