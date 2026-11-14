import { DAY_STATUS_LABELS, DAY_STATUS_STYLES, STAGE_OPTIONS, formatDay } from './helpers';

const STAGE_STYLES = {
  planned: 'bg-stone-100 text-stone-600',
  formation: 'bg-sky-50 text-sky-700',
  stabilization: 'bg-violet-50 text-violet-700',
  integrated: 'bg-emerald-50 text-emerald-700',
  recovery: 'bg-amber-50 text-amber-700'
};

export function StageBadge({ stage, label }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        STAGE_STYLES[stage] || 'bg-stone-100 text-stone-600'
      }`}
    >
      {label || STAGE_OPTIONS.find((option) => option.value === stage)?.label || stage}
    </span>
  );
}

export function ModeBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-lime-50 px-2.5 py-0.5 text-xs font-medium text-lime-700">
      режим мінімуму
    </span>
  );
}

export function DayStatusPill({ day }) {
  if (!day) {
    return <span className="text-xs text-gray-400">Сьогодні ще без запису</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-700" data-testid="today-status">
      <span className={`h-2.5 w-2.5 rounded-full ${DAY_STATUS_STYLES[day.status] || 'bg-stone-200'}`} aria-hidden="true" />
      {day.status_label || DAY_STATUS_LABELS[day.status] || day.status}
    </span>
  );
}

/** Row of small coloured squares, oldest first. */
export function StatusStrip({ days }) {
  if (!days?.length) return null;
  return (
    <div className="flex flex-wrap gap-1" role="list" aria-label="Статуси останніх днів">
      {days.map((day) => {
        const text = `${formatDay(day.date)} — ${day.status_label || DAY_STATUS_LABELS[day.status] || day.status}`;
        return (
          <span
            key={day.date}
            role="listitem"
            title={text}
            aria-label={text}
            className={`h-4 w-4 rounded-[4px] ${DAY_STATUS_STYLES[day.status] || 'bg-stone-200'}`}
          />
        );
      })}
    </div>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-gray-500">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-gray-400">{hint}</span>}
    </label>
  );
}
