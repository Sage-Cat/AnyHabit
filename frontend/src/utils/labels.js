import { formatDate } from './date';
import { plural } from './plural';

const PERIOD_FORMS = {
  day: ['день', 'дні', 'днів'],
  week: ['тиждень', 'тижні', 'тижнів'],
  month: ['місяць', 'місяці', 'місяців'],
  year: ['рік', 'роки', 'років']
};

const PERIOD_WORD_TO_UNIT = { days: 'day', weeks: 'week', months: 'month', years: 'year' };

/**
 * The API describes a streak's unit as "days", "weeks" or "3-week windows".
 * These are shown to the user, so they are turned into Ukrainian here.
 */
export const localizePeriodLabel = (label) => {
  const raw = String(label ?? '').trim();
  const unit = PERIOD_WORD_TO_UNIT[raw];
  if (unit) return PERIOD_FORMS[unit][2];

  const windowMatch = raw.match(/^(\d+)-(day|week|month|year) windows$/);
  if (windowMatch) {
    const count = Number(windowMatch[1]);
    return `періоди по ${count} ${plural(count, PERIOD_FORMS[windowMatch[2]])}`;
  }
  return raw;
};

const MODE_LABELS = {
  'Time based': 'За часом',
  'From logs': 'За записами',
  'No impact configured': 'Вплив не налаштовано'
};

/** Impact mode text from the dashboard API. */
export const localizeModeLabel = (label) => MODE_LABELS[label] || label;

/** Weekdays in the API's order, Monday first. */
export const WEEKDAY_NAMES = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', "П'ятниця", 'Субота', 'Неділя'];
export const WEEKDAY_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'];

/** Short axis label ("4 бер.") for a `YYYY-MM-DD` chart date. */
export const formatChartDate = (value) => formatDate(value, { month: 'short', day: 'numeric', timeZone: 'UTC' });
