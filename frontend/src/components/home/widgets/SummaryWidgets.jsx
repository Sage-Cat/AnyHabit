import { Flame, RefreshCcw } from 'lucide-react';
import { useMemo } from 'react';
import { localizeModeLabel, localizePeriodLabel } from '../../../utils/labels';
import { formatImpact, formatValue, categoryLabel } from './helpers';

export function ImpactSummaryWidget({
  selectedTrackers,
  impactRows,
  isRefreshing,
  onRefresh,
  onOpenTracker,
  sourceLabel
}) {
  const rows = useMemo(
    () =>
      selectedTrackers.map((tracker) => {
        const impact = impactRows.find((row) => row.tracker.id === tracker.id);

        return {
          tracker,
          mainAmount: impact?.main_amount ?? 0,
          impactValue: impact?.impact_value ?? 0,
          modeLabel: localizeModeLabel(impact?.mode_label ?? 'No impact configured')
        };
      }),
    [selectedTrackers, impactRows]
  );

  const totalsByUnit = useMemo(
    () =>
      rows.reduce((acc, row) => {
        const impactUnit = (row.tracker.impact_unit || '$').trim() || '$';
        acc[impactUnit] = (acc[impactUnit] || 0) + row.impactValue;
        return acc;
      }, {}),
    [rows]
  );

  if (!selectedTrackers.length) {
    return (
      <div className="h-full flex items-center justify-center text-center text-gray-500 px-4">
        <div>
          <p className="font-medium text-stone-700">Звичок не вибрано</p>
          <p className="text-sm mt-1">Відкрийте налаштування віджета й оберіть звички.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {sourceLabel && <p className="text-xs text-gray-500">{sourceLabel}</p>}

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex flex-wrap gap-2">
          {Object.entries(totalsByUnit).map(([unit, value]) => (
            <div key={unit} className="px-3 py-1.5 rounded-xl bg-stone-100 text-stone-800 text-sm font-medium">
              Разом: {formatImpact(value)} {unit}
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={onRefresh}
          className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-stone-700 hover:bg-stone-50 transition-colors inline-flex items-center gap-1"
        >
          <RefreshCcw size={13} className={isRefreshing ? 'animate-spin' : ''} />
          Оновити
        </button>
      </div>

      <div className="space-y-2 overflow-y-auto pr-1">
        {rows.map((row) => {
          const impactUnit = row.tracker.impact_unit || '$';

          return (
            <button
              key={row.tracker.id}
              type="button"
              onClick={() => onOpenTracker(row.tracker)}
              className="w-full text-left p-3 rounded-xl border border-gray-200 hover:border-stone-300 hover:bg-stone-50 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-stone-900 truncate">{row.tracker.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {categoryLabel(row.tracker.category)} · {row.modeLabel}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Основа: {formatValue(row.mainAmount)} {row.tracker.unit}
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-sm font-semibold text-stone-900">
                    {formatImpact(row.impactValue)} {impactUnit}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">Загальний вплив</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function TrackerOverviewWidget({ overview }) {
  const total = overview?.total ?? 0;
  const active = overview?.active ?? 0;
  const stopped = overview?.paused ?? Math.max(0, total - active);
  const categoryCount = overview?.categories ?? 0;
  const byType = overview?.by_type || { quit: 0, build: 0, boolean: 0 };

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <StatTile label="Усього" value={total} />
        <StatTile label="Активні" value={active} />
        <StatTile label="На паузі" value={stopped} />
        <StatTile label="Категорії" value={categoryCount} />
      </div>

      <div className="rounded-2xl border border-gray-100 bg-stone-50 p-3 text-sm text-stone-700 space-y-1">
        <p>Відмова: {byType.quit || 0}</p>
        <p>Накопичення: {byType.build || 0}</p>
        <p>Так/ні: {byType.boolean || 0}</p>
      </div>
    </div>
  );
}

export function CategoryBreakdownWidget({ categories, onOpenCategory }) {
  const rows = categories || [];

  if (!rows.length) {
    return <div className="h-full flex items-center justify-center text-sm text-gray-500">Категорій ще немає.</div>;
  }

  const maxCount = Math.max(...rows.map((row) => row.count));

  return (
    <div className="h-full flex flex-col gap-2">
      {rows.map((row) => (
        <button
          key={row.category}
          type="button"
          onClick={() => onOpenCategory(row.category)}
          className="w-full text-left rounded-xl border border-gray-200 px-3 py-2 hover:bg-stone-50 transition-colors"
        >
          <div className="flex items-center justify-between text-sm text-stone-700">
            <span className="font-medium truncate">{categoryLabel(row.category)}</span>
            <span className="text-xs text-gray-500">{row.count}</span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-stone-700"
              style={{ width: `${Math.max(8, (row.count / maxCount) * 100)}%` }}
            />
          </div>
        </button>
      ))}
    </div>
  );
}

export function TopImpactWidget({ rows, onOpenTracker }) {
  const topRows = rows || [];

  if (!topRows.length) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-gray-500">Вплив ще не налаштовано.</div>
    );
  }

  return (
    <div className="h-full space-y-2">
      {topRows.map((row, index) => (
        <button
          key={row.tracker.id}
          type="button"
          onClick={() => onOpenTracker(row.tracker)}
          className="w-full text-left rounded-xl border border-gray-200 px-3 py-2 hover:bg-stone-50 transition-colors"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-stone-900 truncate">
                #{index + 1} {row.tracker.name}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">{categoryLabel(row.tracker.category)}</p>
            </div>

            <div className="text-right">
              <p className="text-sm font-semibold text-stone-900">
                {formatImpact(row.month_impact)} {row.tracker.impact_unit || '$'}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">оцінка на місяць</p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

export function TodayFocusWidget({ rows, overview, isLoading, onOpenTracker }) {
  const pending = useMemo(
    () =>
      rows
        .filter(
          (row) =>
            row.tracker.is_active &&
            !row.tracker.archived_at &&
            row.tracker.type !== 'quit' &&
            row.progress_percentage < 100
        )
        .sort((a, b) => b.progress_percentage - a.progress_percentage),
    [rows]
  );

  if (isLoading) {
    return <div className="flex h-full items-center justify-center text-sm text-gray-500">Завантаження…</div>;
  }

  const done = overview?.completed_today ?? 0;
  const due = overview?.due_today ?? 0;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-gray-100 bg-stone-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Виконано за цей період</p>
        <p className="mt-1 text-2xl font-semibold text-stone-900">
          {done}
          <span className="text-base font-normal text-gray-400"> / {due}</span>
        </p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all"
            style={{ width: `${due > 0 ? Math.min(100, (done / due) * 100) : 0}%` }}
          />
        </div>
      </div>

      {pending.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-center text-sm text-gray-500">
          {due > 0 ? 'Наразі все виконано. Чудово.' : 'Активних регулярних звичок немає.'}
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto pr-1">
          {pending.map((row) => (
            <button
              key={row.tracker.id}
              type="button"
              onClick={() => onOpenTracker(row.tracker)}
              className="w-full rounded-xl border border-gray-200 px-3 py-2 text-left transition-colors hover:bg-stone-50"
            >
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="min-w-0 flex-1 truncate font-medium text-stone-900">{row.tracker.name}</span>
                <span className="shrink-0 text-xs text-gray-500">{Math.round(row.progress_percentage)}%</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-stone-700"
                  style={{ width: `${Math.min(100, row.progress_percentage)}%` }}
                />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function StreaksWidget({ rows, onOpenTracker }) {
  const streaks = useMemo(
    () =>
      rows
        .filter((row) => !row.tracker.archived_at && row.current_streak > 0)
        .sort((a, b) => b.current_streak - a.current_streak)
        .slice(0, 8),
    [rows]
  );

  if (!streaks.length) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center text-sm text-gray-500">
        Активних серій ще немає. Додайте запис сьогодні, щоб розпочати серію.
      </div>
    );
  }

  return (
    <div className="h-full space-y-2 overflow-y-auto">
      {streaks.map((row) => (
        <button
          key={row.tracker.id}
          type="button"
          onClick={() => onOpenTracker(row.tracker)}
          className="flex w-full items-center justify-between gap-3 rounded-xl border border-gray-200 px-3 py-2 text-left transition-colors hover:bg-stone-50"
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-stone-900">{row.tracker.name}</span>
            <span className="block text-xs text-gray-500">{categoryLabel(row.tracker.category)}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1.5 text-stone-900">
            <Flame size={15} className="text-amber-500" />
            <span className="text-lg font-semibold">{row.current_streak}</span>
            <span className="text-xs text-gray-400">{localizePeriodLabel(row.streak_label)}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

function StatTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-stone-50 p-3">
      <p className="text-xs uppercase tracking-wide text-gray-400 font-semibold">{label}</p>
      <p className="text-2xl font-semibold text-stone-900 mt-1">{value}</p>
    </div>
  );
}
