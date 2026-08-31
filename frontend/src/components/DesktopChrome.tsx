import { ReactNode, useState } from "react";
import type { HubModuleInfo, HubToolInfo } from "../api";

type DesktopChromeProps = {
  children: ReactNode;
  projectName: string;
  status: string;
  backendReady: boolean;
  storageRuns: number;
  modules: HubModuleInfo[];
  activeModule: string;
  activeModuleInfo?: HubModuleInfo;
  tools: HubToolInfo[];
  activeTool: string;
  onModule: (id: string) => void;
  onTool: (id: string, title: string) => void;
  onSave: () => void;
  onExport: () => void;
  onAction: (action: string) => void;
  onStatus: (message: string) => void;
};

const menus = [
  { label: "Arquivo", items: [["new-project", "Novo projeto"], ["open-project", "Abrir projeto local"], ["save", "Salvar"], ["export", "Exportar"]] },
  { label: "Projetos", items: [["project", "Projeto atual"], ["history", "Histórico de execuções"], ["batch", "Experimentos em lote"]] },
  { label: "Modelos", items: [["simple", "Simple Macro"], ["economy-zero", "Economy Zero"], ["advanced", "Hybrid / Advanced"], ["profiles", "Profiles"]] },
  { label: "Cenários", items: [["scenario-ai", "Cenário em linguagem natural"], ["shocks", "Choques programados"], ["presets", "Presets"]] },
  { label: "Simulação", items: [["simulation", "Executar"], ["batch", "Comparar execuções"], ["replay", "Reprodutibilidade"]] },
  { label: "Módulos externos", items: [["dynare", "Dynare"], ["minsky", "Minsky"], ["mesa", "Mesa"], ["hark", "HARK"], ["validation", "Compatibilidade"]] },
  { label: "Dados e calibração", items: [["data", "Fontes públicas"], ["calibration", "Metas"], ["calibration", "Ajuste limitado"]] },
  { label: "Resultados", items: [["results", "Painel de resultados"], ["results", "Auditoria SFC/Godley"], ["export", "Exportações"]] },
  { label: "Ajuda", items: [["help", "Documentação local"], ["about", "Sobre o Economy Lab"]] },
];

const moduleGlyphs: Record<string, string> = {
  simulation: "△",
  dynare: "Σ",
  minsky: "⌘",
  mesa: "▦",
  hark: "◉",
  analytics: "▥",
  "scenario-ai": "✦",
  "data-calibration": "◆",
  validation: "✓",
};

function moduleState(module: HubModuleInfo) {
  if (module.available) return { className: "ready", label: "disponível" };
  if (module.status.toLowerCase().includes("offline")) return { className: "offline", label: "offline" };
  if (module.dependencies.length) return { className: "missing", label: "não instalado" };
  return { className: "optional", label: "opcional" };
}

export function DesktopChrome({
  children, projectName, status, backendReady, storageRuns, modules, activeModule,
  activeModuleInfo, tools, activeTool, onModule, onTool, onSave, onExport, onAction, onStatus,
}: DesktopChromeProps) {
  const [navOpen, setNavOpen] = useState(true);
  const [openMenu, setOpenMenu] = useState<number | null>(null);

  return <main className="desktopApp">
    <div className="desktopTopbar">
      <div className="brandMark" aria-hidden="true">△</div>
      <strong>Economy Lab</strong><span className="buildLabel">2.12.1</span>
      <span className="topDivider" />
      <span className="topLabel">Projeto:</span><strong className="projectName">{projectName || "Projeto não salvo"}</strong>
      <span className="localBadge">SQLite local</span>
      <span className="saveState"><i /> Salvo localmente</span>
      <span className={backendReady ? "backendState ready" : "backendState missing"}><i /> {backendReady ? "Backend local pronto" : "Backend indisponível"}</span>
      <span className="topSpacer" />
      <button type="button" className="topAction primary" onClick={onSave}>Salvar</button>
      <button type="button" className="iconAction" title="Exportar" onClick={onExport}>⇩</button>
      <button type="button" className="iconAction" title="Configurações" onClick={() => onStatus("Configurações do laboratório")}>⚙</button>
      <button type="button" className="iconAction" title="Ajuda" onClick={() => onStatus("Documentação local do Economy Lab")}>?</button>
    </div>

    <div className="desktopMenubar">
      {menus.map((menu, index) => <div className="menuRoot" key={menu.label}>
        <button type="button" className={openMenu === index ? "menuButton open" : "menuButton"} onClick={() => setOpenMenu(openMenu === index ? null : index)}>{menu.label}</button>
        {openMenu === index && <div className="menuPopover">
          {menu.items.map(([action, item]) => <button type="button" key={`${action}-${item}`} onClick={() => { if (action === "save") onSave(); else if (action === "export") onExport(); else onAction(action); setOpenMenu(null); }}><span>{item}</span><small>›</small></button>)}
        </div>}
      </div>)}
      <span className="topSpacer" />
      <span>{storageRuns} execuções</span><span>Ledger/SFC: autoridade contábil única</span>
    </div>

    <div className="desktopBody">
      <aside className={navOpen ? "moduleSidebar" : "moduleSidebar collapsed"}>
        <div className="sidebarHeading"><span>{navOpen ? "MÓDULOS" : ""}</span><button type="button" onClick={() => setNavOpen(!navOpen)} title={navOpen ? "Recolher navegação" : "Expandir navegação"}>☰</button></div>
        <nav aria-label="Módulos do Economy Lab">
          {modules.map(module => {
            const state = moduleState(module);
            return <button type="button" key={module.id} className={activeModule === module.id ? "sidebarModule active" : "sidebarModule"} onClick={() => onModule(module.id)} title={!navOpen ? module.title : undefined}>
              <span className="moduleGlyph" aria-hidden="true">{moduleGlyphs[module.id] ?? "□"}</span>
              {navOpen && <span className="sidebarModuleText">{module.title}</span>}
              <i className={`moduleDot ${state.className}`} title={state.label} />
            </button>;
          })}
        </nav>
        {navOpen && <div className="stateLegend"><strong>LEGENDA DE ESTADO</strong><span><i className="moduleDot ready" /> disponível</span><span><i className="moduleDot offline" /> configurado, offline</span><span><i className="moduleDot missing" /> não instalado</span><span><i className="moduleDot optional" /> opcional</span></div>}
      </aside>

      <section className="desktopWorkspace">
        <div className="workspaceToolbar">
          <div className="workspaceIdentity"><strong>{activeModuleInfo?.title ?? "Economy Lab"}</strong><span>{activeModuleInfo?.description ?? "Laboratório econômico local"}</span></div>
          {tools.length > 0 && <nav className="workspaceTools" aria-label={`Ferramentas de ${activeModule}`}>
            {tools.map(tool => <button type="button" key={tool.id} className={activeTool === tool.id ? "workspaceTool active" : "workspaceTool"} onClick={() => onTool(tool.id, tool.title)} title={tool.description}>{tool.title}</button>)}
          </nav>}
        </div>
        <div className="desktopContent">{children}</div>
        <footer className="desktopStatusbar"><span>{status}</span><span className="topSpacer" /><span>Local-first</span><span>Seed auditável</span><span>SFC/Godley</span></footer>
      </section>
    </div>
  </main>;
}
