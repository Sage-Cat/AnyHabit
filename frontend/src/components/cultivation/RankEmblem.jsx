import { Crown, Flame, Footprints, Leaf, Moon, Sparkles, Sprout, Star } from 'lucide-react';

// One emblem per step of the default ladder: Смертний, Адепт 1–3, Маг 1–4.
// A longer custom ladder reuses the last emblem.
const EMBLEMS = [
  { Icon: Footprints, tone: 'from-stone-300 to-stone-500' },
  { Icon: Sprout, tone: 'from-lime-300 to-emerald-500' },
  { Icon: Leaf, tone: 'from-emerald-400 to-teal-600' },
  { Icon: Flame, tone: 'from-amber-400 to-orange-600' },
  { Icon: Sparkles, tone: 'from-violet-400 to-fuchsia-600' },
  { Icon: Star, tone: 'from-sky-400 to-indigo-600' },
  { Icon: Moon, tone: 'from-indigo-400 to-purple-700' },
  { Icon: Crown, tone: 'from-yellow-300 to-amber-600' }
];

const SIZES = {
  xs: ['h-6 w-6 rounded-md', 13],
  sm: ['h-8 w-8 rounded-lg', 16],
  md: ['h-12 w-12 rounded-xl', 24],
  lg: ['h-16 w-16 rounded-2xl', 32]
};

function RankEmblem({ index, size = 'md', label, className = '' }) {
  const safeIndex = Math.min(Math.max(Number(index) || 0, 0), EMBLEMS.length - 1);
  const { Icon, tone } = EMBLEMS[safeIndex];
  const [box, iconSize] = SIZES[size] || SIZES.md;
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center bg-linear-to-br text-white shadow-sm ${tone} ${box} ${className}`}
      {...(label ? { role: 'img', 'aria-label': label, title: label } : { 'aria-hidden': 'true' })}
    >
      <Icon size={iconSize} strokeWidth={2} aria-hidden="true" />
    </span>
  );
}

export default RankEmblem;
