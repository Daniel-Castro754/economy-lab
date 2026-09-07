import { isTauri } from "@tauri-apps/api/core";

type PathFieldProps = {
  label: string;
  value: string;
  placeholder: string;
  kind: "file" | "folder";
  onChange: (value: string) => void;
};

export function PathField({ label, value, placeholder, kind, onChange }: PathFieldProps) {
  const nativeBrowseAvailable = isTauri();

  async function browse() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selection = await open({ directory: kind === "folder", multiple: false });
    if (typeof selection === "string") onChange(selection);
  }

  return <label className="settingsField pathField">
    <span>{label}</span>
    <div className="pathFieldRow">
      <input value={value} placeholder={placeholder} onChange={event => onChange(event.target.value)} />
      {nativeBrowseAvailable && <button type="button" className="secondaryButton" onClick={() => void browse()}>Procurar…</button>}
    </div>
  </label>;
}
