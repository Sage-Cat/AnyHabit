export const TRACKER_TYPE_OPTIONS = [
  { value: 'quit', label: 'Відмова', hint: 'Кинути щось. Рахує час без цього.' },
  { value: 'build', label: 'Накопичення', hint: 'Робити щось частіше. Рахує внесені кількості.' },
  { value: 'boolean', label: 'Так/ні', hint: 'Просто зроблено чи ні за кожен період.' }
];

export const PERIOD_OPTIONS = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Тиждень' },
  { value: 'month', label: 'Місяць' },
  { value: 'year', label: 'Рік' }
];

/** Accent colours a tracker can be tagged with, for scanning a long list. */
export const TRACKER_COLORS = [
  { value: '', label: 'Типовий', swatch: '#a8a29e' },
  { value: 'emerald', label: 'Смарагдовий', swatch: '#10b981' },
  { value: 'sky', label: 'Блакитний', swatch: '#0ea5e9' },
  { value: 'violet', label: 'Фіолетовий', swatch: '#8b5cf6' },
  { value: 'amber', label: 'Бурштиновий', swatch: '#f59e0b' },
  { value: 'rose', label: 'Рожевий', swatch: '#f43f5e' }
];

export const TRACKER_COLOR_HEX = TRACKER_COLORS.reduce((accumulator, option) => {
  if (option.value) accumulator[option.value] = option.swatch;
  return accumulator;
}, {});

export const WEEK_START_OPTIONS = [
  { value: 'monday', label: 'Понеділок' },
  { value: 'sunday', label: 'Неділя' },
  { value: 'saturday', label: 'Субота' }
];

export const MOOD_LABELS = {
  1: 'Дуже погано',
  2: 'Погано',
  3: 'Нейтрально',
  4: 'Добре',
  5: 'Дуже добре'
};

export const DEFAULT_TRACKER_FORM = {
  id: null,
  name: '',
  description: '',
  color: '',
  category: 'General',
  type: 'quit',
  unit: '',
  impact_amount: 0,
  impact_unit: '$',
  impact_per: 'day',
  units_per_amount: 0,
  units_per: 'day',
  units_per_interval: 1,
  is_active: true,
  start_date: '',
  group_id: null,
  participant_ids: []
};

export const DEFAULT_JOURNAL_FORM = { id: null, content: '', mood: 3 };

export const DEFAULT_LOG_FORM = {
  amount: 1,
  note: '',
  timestamp: new Date().toISOString()
};

/** Display names for stored tracker types and periods. */
export const TRACKER_TYPE_LABELS = Object.fromEntries(TRACKER_TYPE_OPTIONS.map((option) => [option.value, option.label]));
export const PERIOD_NOUNS = { day: 'день', week: 'тиждень', month: 'місяць', year: 'рік' };

/** Display names for stored group roles. */
export const ROLE_LABELS = { owner: 'власник', admin: 'адміністратор', member: 'учасник' };
