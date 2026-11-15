import { TRACKER_COLOR_HEX } from '../../constants/tracker';

// Used for habits whose tracker has no colour of its own. Picked by habit id,
// so a habit keeps its colour when others are added, archived or reordered.
const FALLBACK = ['#10b981', '#0ea5e9', '#8b5cf6', '#f59e0b', '#f43f5e', '#14b8a6', '#ec4899', '#84cc16'];

/** `{ habitId: '#rrggbb' }` for the habits of a statistics response. */
export function habitColorMap(habits) {
  const own = Object.fromEntries((habits || []).map((habit) => [habit.id, TRACKER_COLOR_HEX[habit.color]]));
  const taken = new Set(Object.values(own).filter(Boolean));
  const pool = FALLBACK.filter((colour) => !taken.has(colour));
  const palette = pool.length ? pool : FALLBACK;
  return Object.fromEntries(
    (habits || []).map((habit) => [
      habit.id,
      own[habit.id] || palette[Math.abs(Number(habit.id) || 0) % palette.length]
    ])
  );
}
