/** Empty level object for a given kind. */
export const emptyLevel = () => ({ wake_by: '', min_sleep_h: '', max_sleep_h: '', min_amount: '' });

export const levelFromSpec = (level) => ({
  wake_by: level?.wake_by ?? '',
  min_sleep_h: level?.min_sleep_h ?? '',
  max_sleep_h: level?.max_sleep_h ?? '',
  min_amount: level?.min_amount ?? ''
});

/** Fields that make sense for the kind, as API keys. */
export const levelKeys = (kind) =>
  kind === 'sleep' ? ['wake_by', 'min_sleep_h', 'max_sleep_h'] : kind === 'build' ? ['min_amount'] : [];

/**
 * Turn form state into an API level. With `nulls`, cleared fields become
 * null so a merge patch removes them from the passport.
 */
export function buildLevel(kind, state, { nulls = false } = {}) {
  const out = {};
  for (const key of levelKeys(kind)) {
    const raw = state[key];
    if (raw === '' || raw === null || raw === undefined) {
      if (nulls) out[key] = null;
    } else {
      out[key] = key === 'wake_by' ? String(raw) : Number(raw);
    }
  }
  return out;
}

export const hasLevelValue = (kind, state) => levelKeys(kind).some((key) => state[key] !== '' && state[key] != null);
