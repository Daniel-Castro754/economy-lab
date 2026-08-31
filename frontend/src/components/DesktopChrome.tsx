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

type IconName = "activity" | "archive" | "brain" | "chart" | "check" | "chevron" |
  "cpu" | "database" | "download" | "file" | "flask" | "folder" | "help" |
  "history" | "menu" | "play" | "robot" | "save" | "settings" | "shield" |
  "sparkles" | "stack" | "table" | "user" | "world";

const iconPaths: Record<IconName, ReactNode> = {
  activity: <path d="M3 12h4l3-9 4 18 3-9h4" />,
  archive: <><path d="M4 7v13h16V7" /><path d="M3 3h18v4H3zM9 11h6" /></>,
  brain: <><path d="M9.5 4a3 3 0 0 0-5 2.2A3 3 0 0 0 3 11a3 3 0 0 0 2 5.8A3 3 0 0 0 9.5 20V4zM14.5 4a3 3 0 0 1 5 2.2A3 3 0 0 1 21 11a3 3 0 0 1-2 5.8 3 3 0 0 1-4.5 3.2V4zM9.5 9H7m7.5 3H18M9.5 15H7" /></>,
  chart: <><path d="M4 19V5M4 19h16" /><path d="m7 15 4-4 3 2 5-6" /></>,
  check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
  chevron: <path d="m8 10 4 4 4-4" />,
  cpu: <><rect x="7" y="7" width="10" height="10" rx="1" /><path d="M9 1v3m6-3v3M9 20v3m6-3v3M20 9h3m-3 5h3M1 9h3m-3 5h3M10 10h4v4h-4z" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
  download: <><path d="M12 3v12m-4-4 4 4 4-4" /><path d="M5 20h14" /></>,
  file: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5M9 13h6m-6 4h6" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" /><path d="M7 16h10" /></>,
  folder: <path d="M3 6h7l2 2h9v11H3z" />,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.7 2.7 0 1 1 4.2 2.2c-1.2.7-1.7 1.2-1.7 2.3M12 17h.01" /></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  play: <><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4z" /></>,
  robot: <><rect x="4" y="7" width="16" height="12" rx="2" /><path d="M12 3v4M8 12h.01M16 12h.01M8 16h8" /></>,
  save: <><path d="M5 3h12l3 3v15H4V3z" /><path d="M8 3v6h8V3M8 21v-7h8v7" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V3h4v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z" /></>,
  shield: <><path d="M12 3 20 6v6c0 5-3.4 8.2-8 9-4.6-.8-8-4-8-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  sparkles: <><path d="m12 3 1.3 3.7L17 8l-3.7 1.3L12 13l-1.3-3.7L7 8l3.7-1.3zM5 14l.8 2.2L8 17l-2.2.8L5 20l-.8-2.2L2 17l2.2-.8zM19 13l.7 1.8 1.8.7-1.8.7L19 18l-.7-1.8-1.8-.7 1.8-.7z" /></>,
  stack: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
  table: <><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M3 9h18M9 4v16" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  world: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
};

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="tablerIcon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>;
}

const moduleIcons: Record<string, IconName> = {
  simulation: "flask", dynare: "chart", minsky: "activity", mesa: "table", hark: "brain",
  analytics: "chart", "scenario-ai": "sparkles", "data-calibration": "database", validation: "shield",
};

type SidebarGroup = { label: string; kind?: "levels" | "local"; modules?: string[] };

const sidebarGroups: SidebarGroup[] = [
  { label: "SIMULATION LAB", kind: "levels" },
  { label: "MODELAGEM", modules: ["scenario-ai", "dynare", "minsky", "mesa", "hark"] },
  { label: "ANÁLISE", modules: ["analytics", "data-calibration", "validation"] },
  { label: "TRABALHO LOCAL", kind: "local" },
];

const localItems: Array<[string, string, IconName]> = [
  ["project", "Projetos", "folder"], ["history", "Histórico", "history"],
  ["profiles", "Profiles", "user"], ["batch", "Experimentos em lote", "stack"], ["export", "Exportações", "download"],
];

function moduleState(module: HubModuleInfo) {
  if (module.available) return { className: "ready", label: "Disponível" };
  if (module.status.toLowerCase().includes("offline")) return { className: "offline", label: "Offline" };
  if (module.dependencies.length) return { className: "missing", label: "Não instalado" };
  return { className: "optional", label: "Opcional" };
}

export function DesktopChrome({
  children, projectName, status, backendReady, storageRuns, modules, activeModule,
  activeModuleInfo, tools, activeTool, onModule, onTool, onSave, onExport, onAction, onStatus,
}: DesktopChromeProps) {
  const [navOpen, setNavOpen] = useState(true);
  const [fileOpen, setFileOpen] = useState(false);
  const simulation = modules.find(module => module.id === "simulation");
  const currentState = activeModuleInfo ? moduleState(activeModuleInfo) : null;
  const activeToolInfo = tools.find(tool => tool.id === activeTool);
  const pageTitle = activeModule === "simulation" && activeToolInfo ? activeToolInfo.title : (activeModuleInfo?.title ?? "Economy Lab");
  const pageDescription = activeModule === "simulation" && activeToolInfo ? activeToolInfo.description : (activeModuleInfo?.description ?? "Laboratório econômico local");

  const action = (id: string) => {
    if (id === "export") onExport(); else onAction(id);
  };

  return <main className="desktopApp">
    <header className="desktopTopbar">
      <div className="brandMark"><Icon name="flask" size={19} /></div>
      <div className="brandName"><strong>Economy Lab</strong><span>v2.13.0</span></div>
      <div className="fileMenuRoot">
        <button type="button" className="topNavButton" onClick={() => setFileOpen(!fileOpen)}>Arquivo <Icon name="chevron" size={14} /></button>
        {fileOpen && <div className="fileMenu">
          {[["new-project", "Novo projeto"], ["open-project", "Abrir projeto local"], ["save", "Salvar projeto"], ["export", "Exportar resultados"]].map(([id, label]) => <button type="button" key={id} onClick={() => { if (id === "save") onSave(); else action(id); setFileOpen(false); }}>{label}</button>)}
        </div>}
      </div>
      <span className="topDivider" />
      <div className="projectContext"><span>Projeto</span><strong>{projectName || "Projeto não salvo"}</strong></div>
      <span className="localBadge"><Icon name="database" size={13} /> SQLite local</span>
      <span className={backendReady ? "backendState ready" : "backendState missing"}><i /> {backendReady ? "Backend pronto" : "Backend indisponível"}</span>
      <span className="topSpacer" />
      <button type="button" className="topAction run" onClick={() => onAction("simulation")}><Icon name="play" size={15} /> Executar</button>
      <button type="button" className="topAction" onClick={onSave}><Icon name="save" size={15} /> Salvar</button>
      <button type="button" className="iconAction" title="Exportar" aria-label="Exportar" onClick={onExport}><Icon name="download" size={17} /></button>
      <button type="button" className="iconAction" title="Configurações" aria-label="Configurações" onClick={() => onStatus("Configurações do laboratório")}><Icon name="settings" size={17} /></button>
      <button type="button" className="iconAction" title="Ajuda" aria-label="Ajuda" onClick={() => onStatus("Consulte README.md e a pasta docs incluídos no pacote completo")}><Icon name="help" size={17} /></button>
    </header>

    <div className="desktopBody">
      <aside className={navOpen ? "moduleSidebar" : "moduleSidebar collapsed"}>
        <div className="sidebarHeading"><span>{navOpen ? "NAVEGAÇÃO" : ""}</span><button type="button" onClick={() => setNavOpen(!navOpen)} title={navOpen ? "Recolher navegação" : "Expandir navegação"}><Icon name="menu" size={16} /></button></div>
        <nav aria-label="Navegação principal do Economy Lab">
          {sidebarGroups.map(group => <div className="sidebarGroup" key={group.label}>
            {navOpen && <div className="sidebarGroupLabel">{group.label}</div>}
            {group.kind === "levels" && ["simple", "economy-zero", "advanced"].map((id, index) => {
              const labels = ["Simple Macro", "Economy Zero", "Hybrid/Advanced"];
              const active = activeModule === "simulation" && (id === "simple" ? activeTool === "simulation-simple" : id === "economy-zero" ? activeTool === "simulation-run" : false);
              const simState = simulation ? moduleState(simulation) : { className: "offline", label: "Offline" };
              return <button type="button" key={id} className={active ? "sidebarModule active" : "sidebarModule"} onClick={() => onAction(id)} title={!navOpen ? labels[index] : undefined}>
                <span className="moduleIcon"><Icon name={index === 0 ? "activity" : index === 1 ? "flask" : "cpu"} size={17} /></span>
                {navOpen && <><span className="sidebarModuleText">{labels[index]}</span><i className={`moduleDot ${simState.className}`} title={simState.label} /></>}
              </button>;
            })}
            {group.modules?.map(id => {
              const module = modules.find(item => item.id === id);
              if (!module) return null;
              const state = moduleState(module);
              return <button type="button" key={id} className={activeModule === id ? "sidebarModule active" : "sidebarModule"} onClick={() => onModule(id)} title={!navOpen ? module.title : undefined}>
                <span className="moduleIcon"><Icon name={moduleIcons[id] ?? "file"} size={17} /></span>
                {navOpen && <><span className="sidebarModuleText">{module.title}</span><i className={`moduleDot ${state.className}`} title={`${module.title}: ${state.label}`} /></>}
              </button>;
            })}
            {group.kind === "local" && localItems.map(([id, label, icon]) => <button type="button" key={id} className="sidebarModule localItem" onClick={() => action(id)} title={!navOpen ? label : undefined}>
              <span className="moduleIcon"><Icon name={icon} size={17} /></span>{navOpen && <span className="sidebarModuleText">{label}</span>}
            </button>)}
          </div>)}
        </nav>
        {navOpen && <div className="ledgerAuthority"><Icon name="shield" size={16} /><span><strong>Ledger/SFC</strong>Autoridade contábil única</span></div>}
      </aside>

      <section className="desktopWorkspace">
        <div className="workspaceHeader">
          <div className="workspaceIdentity">
            <span className="workspaceEyebrow">ECONOMY LAB / {activeModuleInfo?.kind?.toUpperCase() ?? "LOCAL"}</span>
            <div className="workspaceTitle"><strong>{pageTitle}</strong>{currentState && <span className={`statusBadge ${currentState.className}`}>{currentState.label}</span>}</div>
            <span className="workspaceDescription">{pageDescription}</span>
          </div>
          <div className="workspaceMeta"><span>{storageRuns} execuções locais</span><span>Seed auditável</span></div>
        </div>
        {tools.length > 0 && <nav className="workspaceTools" aria-label={`Ferramentas de ${activeModule}`}>
          {tools.map(tool => <button type="button" key={tool.id} className={activeTool === tool.id ? "workspaceTool active" : "workspaceTool"} onClick={() => onTool(tool.id, tool.title)} title={tool.description}>{tool.title}</button>)}
        </nav>}
        <div className="desktopContent">{children}</div>
        <footer className="desktopStatusbar"><Icon name={backendReady ? "check" : "activity"} size={14} /><span>{status}</span><span className="topSpacer" /><span>Local-first</span><span>v2.13.0</span></footer>
      </section>
    </div>
  </main>;
}
