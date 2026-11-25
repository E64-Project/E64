// IDs remain stable; only visible text uses filesystem labels.
const labels = new Map();
export function rememberVolumes(volumes) {
  labels.clear();
  for (const v of volumes || []) if (typeof v.label === "string")
    labels.set(v.id, v.label.replace(/[\x00-\x1f\x7f]/g, "").slice(0, 255));
}
export function volumeLabel(id) {
  const base = id === "USB" ? "USB1" : id;
  const label = labels.get(id);
  return label && id !== "SD" ? base + ": " + label : base;
}
