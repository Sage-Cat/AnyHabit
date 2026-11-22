import { TriangleAlert } from 'lucide-react';
import { DAY_STATUS_LABELS, STAGE_OPTIONS, dayLabel, dayStyle, formatDay } from './helpers';

const STAGE_STYLES = {
  planned: 'bg-stone-100 text-stone-600',
  formation: 'bg-sky-50 text-sky-700',
  stabilization: 'bg-violet-50 text-violet-700',
  integrated: 'bg-emerald-50 text-emerald-700'
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

/** «Рівень N» next to the stage; only for habits with more than one rung. */
export function LevelBadge({ ladder }) {
  if (!ladder || !(ladder.count > 1)) return null;
  return (
    <span
      className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
      data-testid="level-badge"
    >
      Рівень {ladder.current}
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
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-700"
      data-testid="today-status"
      data-warning={day.warning ? 'true' : undefined}
      title={day.warning || undefined}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${dayStyle(day)}`} aria-hidden="true" />
      {day.status_label || DAY_STATUS_LABELS[day.status] || day.status}
      {day.warning && (
        <span className="inline-flex items-center gap-0.5 text-amber-700">
          <TriangleAlert size={12} aria-hidden="true" /> попередження
        </span>
      )}
    </span>
  );
}

/** Row of small coloured squares, oldest first. */
export function StatusStrip({ days }) {
  if (!days?.length) return null;
  return (
    <div className="flex flex-wrap gap-1" role="list" aria-label="Статуси останніх днів">
      {days.map((day) => {
        const text = `${formatDay(day.date)} — ${dayLabel(day)}`;
        return (
          <span
            key={day.date}
            role="listitem"
            title={text}
            aria-label={text}
            className={`h-4 w-4 rounded-[4px] ${dayStyle(day)}`}
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
