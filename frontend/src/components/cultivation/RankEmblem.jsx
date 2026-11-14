// Rank emblems: game-icons.net shapes (CC BY 3.0, see assets/ranks/CREDITS.md)
// drawn as a white mask on a gradient tile, one per step of the default ladder.
// A longer custom ladder reuses the last emblem.
const ICONS = import.meta.glob('../../assets/ranks/*.svg', { eager: true, query: '?url', import: 'default' });
const ICON_URLS = Object.keys(ICONS)
  .sort()
  .map((path) => ICONS[path]);

const TONES = [
  'from-stone-300 to-stone-500',
  'from-lime-300 to-emerald-500',
  'from-emerald-400 to-teal-600',
  'from-teal-400 to-cyan-600',
  'from-sky-400 to-blue-600',
  'from-orange-400 to-red-600',
  'from-violet-400 to-fuchsia-600',
  'from-amber-300 to-orange-500',
  'from-cyan-300 to-indigo-600',
  'from-indigo-500 to-slate-900',
  'from-blue-500 to-violet-800',
  'from-rose-400 to-purple-700',
  'from-purple-700 to-zinc-900',
  'from-yellow-300 to-amber-600'
];

const SIZES = {
  xs: 'h-7 w-7 rounded-md p-1',
  sm: 'h-9 w-9 rounded-lg p-1.5',
  md: 'h-12 w-12 rounded-xl p-2',
  lg: 'h-16 w-16 rounded-2xl p-2.5'
};

function RankEmblem({ index, size = 'md', label, className = '' }) {
  const safeIndex = Math.min(Math.max(Number(index) || 0, 0), ICON_URLS.length - 1);
  const url = ICON_URLS[safeIndex];
  const tone = TONES[Math.min(safeIndex, TONES.length - 1)];
  const mask = `url("${url}") center / contain no-repeat`;
  return (
    <span
      className={`inline-flex shrink-0 bg-linear-to-br shadow-sm ${tone} ${SIZES[size] || SIZES.md} ${className}`}
      data-rank-emblem={safeIndex}
      {...(label ? { role: 'img', 'aria-label': label, title: label } : { 'aria-hidden': 'true' })}
    >
      {/* Inline colour: the dark theme repaints .bg-white. */}
      <span className="block h-full w-full" style={{ backgroundColor: '#fff', mask, WebkitMask: mask }} />
    </span>
  );
}

export default RankEmblem;
