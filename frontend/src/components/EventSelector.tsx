const EVENTS = Array.from({ length: 12 }, (_, i) => `EVT${String(i + 1).padStart(4, "0")}`);

interface Props {
  value: string | null;
  onChange: (eventId: string) => void;
  disabled?: boolean;
}

export default function EventSelector({ value, onChange, disabled }: Props) {
  return (
    <label className="event-selector">
      <span>Event</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        <option value="" disabled>
          Select a spill event…
        </option>
        {EVENTS.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
    </label>
  );
}
