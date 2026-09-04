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

const ICON: Record<StageStatus, string> = {
  idle: "○",
  loading: "◐",
  done: "●",
  error: "✕",
};

interface Props {
  status: Record<StageKey, StageStatus>;
  errors: Partial<Record<StageKey, string>>;
}

export default function PipelineStatus({ status, errors }: Props) {
  return (
    <div className="pipeline-status" role="status">
      {(Object.keys(LABELS) as StageKey[]).map((key) => (
        <span
          key={key}
          className={`stage stage-${status[key]}`}
          title={errors[key] ? `${LABELS[key]}: ${errors[key]}` : LABELS[key]}
        >
          <span className="stage-icon">{ICON[status[key]]}</span>
          {LABELS[key]}
        </span>
      ))}
    </div>
  );
}
