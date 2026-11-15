import { useCallback, useEffect, useState } from 'react';
import { fetchOverviewApi } from '../../services/cultivationApi';
import { formatNumber } from '../../utils/number';

export const STAGE_OPTIONS = [
  { value: 'planned', label: 'Заплановано' },
  { value: 'formation', label: 'Формування' },
  { value: 'stabilization', label: 'Стабілізація' },
  { value: 'integrated', label: 'Інтегровано' }
];

export const KIND_OPTIONS = [
  { value: 'sleep', label: 'Сон' },
  { value: 'build', label: 'Накопичення' },
  { value: 'boolean', label: 'Так/ні' },
  { value: 'quit', label: 'Відмова' }
];

export const KIND_LABELS = Object.fromEntries(KIND_OPTIONS.map((kind) => [kind.value, kind.label]));

// One colour per day status; the label always travels with it (title / text),
// so colour is never the only carrier of meaning.
export const DAY_STATUS_STYLES = {
  success: 'bg-emerald-500',
  minimum: 'bg-lime-300',
  fail: 'bg-rose-500',
  exception: 'bg-sky-300',
  no_data: 'bg-stone-200',
  unrated: 'bg-amber-200',
  invalid: 'bg-stone-400'
};

// Mirrors the backend's labels so the legend matches the tooltips.
export const DAY_STATUS_LABELS = {
  success: 'Успіх',
  minimum: 'Мінімум',
  fail: 'Порушення',
  exception: 'Виняток',
  no_data: 'Немає даних',
  unrated: 'Без критерію',
  invalid: 'Перевірити запис'
};

// A success inside the tolerance band counts, but is shown apart from a clean one.
export const WARNING_STYLE = 'bg-amber-400';
export const WARNING_LABEL = 'Успіх з попередженням';

export const dayStyle = (day) =>
  day?.status === 'success' && day?.warning ? WARNING_STYLE : DAY_STATUS_STYLES[day?.status] || 'bg-stone-200';

export const dayLabel = (day) => {
  const label = day?.status_label || DAY_STATUS_LABELS[day?.status] || day?.status;
  return day?.status === 'success' && day?.warning ? `${WARNING_LABEL}: ${day.warning}` : label;
};

export const INPUT_CLASS =
  'w-full rounded-xl border border-gray-200 bg-stone-50 p-2.5 text-sm outline-none focus:border-stone-400';
export const BUTTON_PRIMARY =
  'rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-50';
export const BUTTON_SECONDARY =
  'rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50';
export const CARD_CLASS = 'rounded-2xl border border-gray-100 bg-white p-5 shadow-sm';

/** A missing value stays a dash; it must never be shown as 0 %. */
export const formatPercent = (value) =>
  value === null || value === undefined ? '—' : `${formatNumber(value * 100, 0)}%`;

export const formatDays = (value) => (value === null || value === undefined ? '—' : `${formatNumber(value, 1)} дн.`);

/**
 * Format a plain `YYYY-MM-DD` day. It is built from local parts on purpose:
 * running it through the API-timestamp parser would read it as UTC midnight
 * and shift the date for viewers west of Greenwich.
 */
export const formatDay = (value, options = { day: 'numeric', month: 'long' }) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
  if (!match) return '—';
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])).toLocaleDateString('uk-UA', options);
};

/** Load the overview and expose a reload. Errors are kept, not thrown. */
export function useCultivationOverview() {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const data = await fetchOverviewApi();
      setOverview(data);
      setError('');
    } catch (loadError) {
      setError(loadError?.message || 'Не вдалося завантажити дані');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { overview, error, isLoading, reload };
}

/**
 * Default values for the sleep entry form: last night 23:00 -> now.
 * The backend reads these naive values in the user's configured timezone, so
 * "now" is taken in that zone (from the overview), not the browser's. It is
 * rounded down to 5 minutes because a wake time in the future is rejected.
 */
export function defaultSleepTimes(timeZone) {
  const pad = (n) => String(n).padStart(2, '0');
  let parts;
  try {
    parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-GB', {
        timeZone: timeZone || undefined,
        hourCycle: 'h23',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
        .formatToParts(new Date())
        .map((part) => [part.type, part.value])
    );
  } catch {
    parts = null;
  }
  const now = parts
    ? { y: +parts.year, mo: +parts.month, d: +parts.day, h: +parts.hour, mi: +parts.minute }
    : (() => {
        const d = new Date();
        return { y: d.getFullYear(), mo: d.getMonth() + 1, d: d.getDate(), h: d.getHours(), mi: d.getMinutes() };
      })();
  // Wall-clock arithmetic on a UTC-based Date, so DST never gets involved.
  const wall = (y, mo, d, h, mi) => new Date(Date.UTC(y, mo - 1, d, h, mi));
  const fmt = (d) =>
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  return {
    bedtime: fmt(wall(now.y, now.mo, now.d - 1, 23, 0)),
    wake: fmt(wall(now.y, now.mo, now.d, now.h, Math.floor(now.mi / 5) * 5))
  };
}
