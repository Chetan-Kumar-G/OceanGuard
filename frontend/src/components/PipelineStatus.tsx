import type { StageKey, StageStatus } from "../hooks/useEventPipeline";

const LABELS: Record<StageKey, string> = {
  f2: "F2 Temporal",
  f3: "F3 Hindcast",
  f4: "F4 AIS",
  f5: "F5 Consistency",
  f6: "F6 Ranking",
  f7: "F7 Graph",
  f8: "F8 Forecast",
};

const STAGE_KEYS = Object.keys(LABELS) as StageKey[];

interface Props {
  status: Record<StageKey, StageStatus>;
  errors: Partial<Record<StageKey, string>>;
}

/** One compact badge instead of seven labeled dots - hover for the per-stage
 * breakdown (native title tooltip, no extra UI). */
export default function PipelineStatus({ status, errors }: Props) {
  const done = STAGE_KEYS.filter((k) => status[k] === "done").length;
  const errored = STAGE_KEYS.filter((k) => status[k] === "error");
  const loading = STAGE_KEYS.some((k) => status[k] === "loading");

  const tooltip = STAGE_KEYS.map((k) => `${LABELS[k]}: ${status[k]}${errors[k] ? ` (${errors[k]})` : ""}`).join("\n");

  const icon = errored.length > 0 ? "✕" : loading ? "◐" : done === STAGE_KEYS.length ? "●" : "○";
  const cls = errored.length > 0 ? "stage-error" : loading ? "stage-loading" : done === STAGE_KEYS.length ? "stage-done" : "";

  return (
    <span className={`pipeline-status-compact ${cls}`} role="status" title={tooltip}>
      <span className="stage-icon">{icon}</span>
      {errored.length > 0 ? `${errored.length} stage${errored.length > 1 ? "s" : ""} failed` : `${done}/${STAGE_KEYS.length} ready`}
    </span>
  );
}
