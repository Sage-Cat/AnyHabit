import { plural } from './plural';

// Forms: one / few / many, in the nominative (for "кожні 3 тижні") and the
// genitive-friendly spelling used after "/" and "цей/ці".
const PERIOD_LABELS = {
  day: { one: 'день', few: 'дні', many: 'днів', noun: 'денна', every: ['день', 'дні', 'днів'], adj: 'цей день' },
  week: { one: 'тиждень', few: 'тижні', many: 'тижнів', noun: 'тижнева', every: ['тиждень', 'тижні', 'тижнів'], adj: 'цей тиждень' },
  month: { one: 'місяць', few: 'місяці', many: 'місяців', noun: 'місячна', every: ['місяць', 'місяці', 'місяців'], adj: 'цей місяць' },
  year: { one: 'рік', few: 'роки', many: 'років', noun: 'річна', every: ['рік', 'роки', 'років'], adj: 'цей рік' }
};

/** Stored default category; shown to the user under a Ukrainian name. */
export const DEFAULT_CATEGORY = 'General';

export const normalizeCategory = (value) => (value || DEFAULT_CATEGORY).trim() || DEFAULT_CATEGORY;

/** Display name of a category (the stored default is kept as-is). */
export const categoryLabel = (value) => {
  const name = normalizeCategory(value);
  return name === DEFAULT_CATEGORY ? 'Загальні' : name;
};

/** "30 сторінок / день", "Щоденна звичка", "Звичка раз на 3 тижні" — the tracker's schedule in words. */
export const formatScheduleLabel = (tracker) => {
  const interval = Math.max(1, Number(tracker.units_per_interval || 1));
  const period = PERIOD_LABELS[tracker.units_per] || PERIOD_LABELS.day;

  if (tracker.type === 'boolean') {
    return interval === 1
      ? `${period.noun.charAt(0).toUpperCase()}${period.noun.slice(1)} звичка`
      : `Звичка раз на ${interval} ${plural(interval, period.every)}`;
  }

  return interval === 1
    ? `${tracker.units_per_amount} ${tracker.unit} / ${period.one}`
    : `${tracker.units_per_amount} ${tracker.unit} / ${interval} ${plural(interval, period.every)}`;
};

/** "цей день", "ці 3 тижні" — names the window a target applies to. */
export const formatWindowLabel = (tracker) => {
  const interval = Math.max(1, Number(tracker.units_per_interval || 1));
  const period = PERIOD_LABELS[tracker.units_per] || PERIOD_LABELS.day;
  return interval === 1 ? period.adj : `ці ${interval} ${plural(interval, period.every)}`;
};
