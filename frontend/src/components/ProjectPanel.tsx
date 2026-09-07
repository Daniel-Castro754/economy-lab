import type { ProjectSummary, RunSummary, StorageStatus } from "../api";

export type ProjectPanelProps = {
  storage: StorageStatus | null;
  projectId: string | null;
  projects: ProjectSummary[];
  projectName: string;
  projectDescription: string;
  runs: RunSummary[];
  disabled: boolean;
  onOpenProject: (id: string) => void;
  onProjectNameChange: (name: string) => void;
  onProjectDescriptionChange: (description: string) => void;
  onSaveProject: () => void;
  onNewProject: () => void;
  onDeleteProject: () => void;
  onOpenRun: (runId: string) => void;
  formatDate: (value: string) => string;
};

export function ProjectPanel({
  storage, projectId, projects, projectName, projectDescription, runs, disabled,
  onOpenProject, onProjectNameChange, onProjectDescriptionChange,
  onSaveProject, onNewProject, onDeleteProject, onOpenRun, formatDate,
}: ProjectPanelProps) {
  return (
    <div className="projectBox" id="economy-zero-projects">
      <div className="projectTitle">
        <strong>Projeto local</strong>
        <span className="muted">SQLite · {storage?.projects ?? 0} projetos · {storage?.runs ?? 0} execuções · {storage?.experiments ?? 0} lotes · {storage?.profiles ?? 0} profiles</span>
      </div>
      <select value={projectId ?? ""} onChange={(e) => onOpenProject(e.target.value)} disabled={disabled}>
        <option value="">Projeto não salvo</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>{project.name} ({project.run_count})</option>
        ))}
      </select>
      <input
        className="numberInput"
        value={projectName}
        maxLength={120}
        placeholder="Nome do projeto"
        onChange={(e) => onProjectNameChange(e.target.value)}
        disabled={disabled}
      />
      <textarea
        rows={2}
        value={projectDescription}
        maxLength={1000}
        placeholder="Descrição opcional"
        onChange={(e) => onProjectDescriptionChange(e.target.value)}
        disabled={disabled}
      />
      <div className="projectActions">
        <button type="button" onClick={onSaveProject} disabled={disabled}>{projectId ? "Salvar alterações" : "Salvar projeto"}</button>
        <button type="button" className="secondaryButton" onClick={onNewProject} disabled={disabled}>Novo</button>
        {projectId && <button type="button" className="dangerButton" onClick={onDeleteProject} disabled={disabled}>Excluir</button>}
      </div>
      {projectId && runs.length > 0 && (
        <div className="runHistory">
          <strong>Histórico recente</strong>
          {runs.slice(0, 6).map((run) => (
            <button type="button" className="runItem" key={run.id} onClick={() => onOpenRun(run.id)} disabled={disabled}>
              <span>{formatDate(run.created_at)}</span>
              <span>PIB {run.final_gdp_index.toFixed(1)} · π {run.final_inflation.toFixed(1)}% · u {run.final_unemployment.toFixed(1)}%</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
