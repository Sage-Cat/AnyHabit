// Stage colours for charts. Inline colours: the dark theme repaints the matching Tailwind classes.
export const STAGE_META = [
  { key: 'planned', label: 'Заплановані', colour: '#a8a29e' },
  { key: 'formation', label: 'Формування', colour: '#38bdf8' },
  { key: 'stabilization', label: 'Стабілізація', colour: '#8b5cf6' },
  { key: 'integrated', label: 'Інтегровані', colour: '#10b981' }
];

export const STAGE_COLOUR = Object.fromEntries(STAGE_META.map((stage) => [stage.key, stage.colour]));

export const DAY_MS = 24 * 60 * 60 * 1000;
export const toTime = (iso) => Date.parse(`${iso}T00:00:00Z`);
export const toIso = (time) => new Date(time).toISOString().slice(0, 10);
