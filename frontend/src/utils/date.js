import { pluralCount } from './plural';

export const DAY_MS = 1000 * 60 * 60 * 24;

/**
 * Parse a timestamp coming from the API.
 *
 * Older rows are serialised without a timezone offset even though they are
 * stored as UTC. Treating those as local time shifted every displayed date by
 * the viewer's offset, so a missing offset is read as UTC here.
 */
export const parseApiDate = (value) => {
  if (!value) return null;
  if (value instanceof Date) return new Date(value);

  const raw = String(value).trim();
  if (!raw) return null;

  const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(raw);
  const parsed = new Date(hasTimezone ? raw : `${raw}Z`);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const formatDate = (value, options = { dateStyle: 'medium' }) => {
  const date = parseApiDate(value);
  return date ? date.toLocaleDateString('uk-UA', options) : '—';
};

export const formatDateTime = (value) => {
  const date = parseApiDate(value);
  return date ? date.toLocaleString('uk-UA', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
};

export const formatTime = (value) => {
  const date = parseApiDate(value);
  return date ? date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) : '—';
};

/** «3 дні тому» style label for activity timestamps. */
export const formatRelative = (value) => {
  const date = parseApiDate(value);
  if (!date) return 'ніколи';

  const diffMs = Date.now() - date.getTime();
  const diffDays = Math.floor(diffMs / DAY_MS);

  if (diffMs < 60_000) return 'щойно';
  if (diffMs < 3_600_000) {
    const minutes = Math.floor(diffMs / 60_000);
    return `${pluralCount(minutes, ['хвилину', 'хвилини', 'хвилин'])} тому`;
  }
  if (diffDays < 1) {
    const hours = Math.floor(diffMs / 3_600_000);
    return `${pluralCount(hours, ['годину', 'години', 'годин'])} тому`;
  }
  if (diffDays === 1) return 'вчора';
  if (diffDays < 30) return `${pluralCount(diffDays, ['день', 'дні', 'днів'])} тому`;

  return date.toLocaleDateString('uk-UA', { dateStyle: 'medium' });
};

/** Value for a `datetime-local` input, which expects local wall-clock time. */
export const toLocalInputValue = (value) => {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return '';

  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}`;
};

/** Value for a `date` input. */
export const toDateInputValue = (value) => {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return '';

  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

/** Timezones offered in Settings, with the browser's own guess pinned first. */
export const getTimezoneOptions = () => {
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const supported =
    typeof Intl.supportedValuesOf === 'function'
      ? Intl.supportedValuesOf('timeZone')
      : [
          'UTC',
          'Europe/London',
          'Europe/Berlin',
          'Europe/Madrid',
          'Europe/Moscow',
          'America/New_York',
          'America/Chicago',
          'America/Denver',
          'America/Los_Angeles',
          'America/Sao_Paulo',
          'Asia/Dubai',
          'Asia/Kolkata',
          'Asia/Shanghai',
          'Asia/Tokyo',
          'Australia/Sydney',
          'Pacific/Auckland'
        ];

  const unique = [...new Set([browserZone, 'UTC', ...supported].filter(Boolean))];
  return { browserZone, options: unique };
};
