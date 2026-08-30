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
  onStatus: (message: string) => void;
};

const menus = [
  { label: "Arquivo", items: ["Novo projeto", "Abrir projeto local", "Salvar", "Exportar"] },
  { label: "Projetos", items: ["Projeto atual", "Histórico de execuções", "Experimentos em lote"] },
  { label: "Modelos", items: ["Simple Macro", "Economy Zero", "Hybrid / Advanced", "Profiles"] },
  { label: "Cenários", items: ["Cenário em linguagem natural", "Choques programados", "Presets"] },
  { label: "Simulação", items: ["Executar", "Comparar execuções", "Reprodutibilidade"] },
  { label: "Módulos externos", items: ["Dynare", "Minsky", "Mesa", "HARK", "Compatibilidade"] },
  { label: "Dados e calibração", items: ["Fontes públicas", "Metas", "Ajuste limitado"] },
  { label: "Resultados", items: ["Painel de resultados", "Auditoria SFC/Godley", "Exportações"] },
  { label: "Ajuda", items: ["Documentação local", "Sobre o Economy Lab"] },
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
  activeModuleInfo, tools, activeTool, onModule, onTool, onStatus,
}: DesktopChromeProps) {
  const [navOpen, setNavOpen] = useState(true);
  const [openMenu, setOpenMenu] = useState<number | null>(null);

  return <main className="desktopApp">
    <div className="desktopTopbar">
      <div className="brandMark" aria-hidden="true">△</div>
      <strong>Economy Lab</strong><span className="buildLabel">2.12.0</span>
      <span className="topDivider" />
      <span className="topLabel">Projeto:</span><strong className="projectName">{projectName || "Projeto não salvo"}</strong>
      <span className="localBadge">SQLite local</span>
      <span className="saveState"><i /> Salvo localmente</span>
      <span className={backendReady ? "backendState ready" : "backendState missing"}><i /> {backendReady ? "Backend local pronto" : "Backend indisponível"}</span>
      <span className="topSpacer" />
      <button type="button" className="topAction primary" onClick={() => onStatus("Projeto salvo localmente")}>Salvar</button>
      <button type="button" className="iconAction" title="Exportar" onClick={() => onStatus("Use as ações de exportação do painel ativo")}>⇩</button>
      <button type="button" className="iconAction" title="Configurações" onClick={() => onStatus("Configurações do laboratório")}>⚙</button>
      <button type="button" className="iconAction" title="Ajuda" onClick={() => onStatus("Documentação local do Economy Lab")}>?</button>
    </div>

    <div className="desktopMenubar">
      {menus.map((menu, index) => <div className="menuRoot" key={menu.label}>
        <button type="button" className={openMenu === index ? "menuButton open" : "menuButton"} onClick={() => setOpenMenu(openMenu === index ? null : index)}>{menu.label}</button>
        {openMenu === index && <div className="menuPopover">
          {menu.items.map(item => <button type="button" key={item} onClick={() => { onStatus(`${item} selecionado`); setOpenMenu(null); }}><span>{item}</span><small>›</small></button>)}
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
