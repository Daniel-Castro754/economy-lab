import type { ProfileSummary, SimulationPresetInfo } from "../api";

export type ProfilePanelProps = {
  presets: SimulationPresetInfo[];
  profiles: ProfileSummary[];
  appliedProfiles: Record<string, string>;
  onApplyPreset: (presetId: string) => void;
  onApplyProfile: (profileId: string) => void;
  onDeleteProfile: (profile: ProfileSummary) => void;
};

export function ProfilePanel({
  presets, profiles, appliedProfiles,
  onApplyPreset, onApplyProfile, onDeleteProfile,
}: ProfilePanelProps) {
  return (
    <div className="profileBox" id="economy-zero-profiles">
      <div className="projectTitle">
        <strong>Motores e Profiles</strong>
        <span className="muted">Basic funciona sem software externo; Profiles trazem configurações dos laboratórios.</span>
      </div>
      <div className="presetGrid">
        {presets.map((preset) => (
          <button type="button" className="secondaryButton" key={preset.id} onClick={() => onApplyPreset(preset.id)} title={preset.description}>
            {preset.title}
          </button>
        ))}
      </div>
      {Object.keys(appliedProfiles ?? {}).length > 0 && (
        <div className="profileChips">
          {Object.entries(appliedProfiles).map(([kind, id]) => { const p = profiles.find(item => item.id === id); return <span key={kind}>{kind}: {p?.name ?? id.slice(0, 8)}</span>; })}
        </div>
      )}
      {profiles.length > 0 ? (
        <div className="profileList">
          {profiles.slice(0, 8).map((profile) => (
            <div className="profileItem" key={profile.id}>
              <div><strong>{profile.name}</strong><small>{profile.module_id} · {profile.kind} · {profile.compatibility}</small></div>
              <div className="projectActions"><button type="button" onClick={() => onApplyProfile(profile.id)}>Aplicar</button><button type="button" className="dangerButton" onClick={() => onDeleteProfile(profile)}>Excluir</button></div>
            </div>
          ))}
        </div>
      ) : <p className="muted">Nenhum Profile salvo ainda. Abra Dynare, Mesa, HARK ou Minsky Lab e use "Salvar e enviar".</p>}
    </div>
  );
}
