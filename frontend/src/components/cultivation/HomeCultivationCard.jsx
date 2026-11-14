import { Moon, Sprout } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import SleepEntryModal from './SleepEntryModal';
import { DayStatusPill, ModeBadge } from './common';
import { BUTTON_PRIMARY, useCultivationOverview } from './helpers';

/**
 * Fixed compact card above the widget grid (not a grid widget). Stays quiet
 * when the overview cannot be loaded, so it never gets in the way of the home page.
 */
function HomeCultivationCard() {
  const { overview, isLoading, error, reload } = useCultivationOverview();
  const [sleepHabit, setSleepHabit] = useState(null);

  if (isLoading || error || !overview) return null;

  const total = overview.active.length + overview.integrated.length + overview.planned.length;
  if (total === 0) {
    return (
      <div className="mb-4 text-sm text-gray-400" data-testid="home-cultivation-invite">
        <Sprout size={14} className="mr-1.5 inline text-emerald-600" aria-hidden="true" />
        Хочете вирощувати звичку поетапно?{' '}
        <Link to="/practice" className="font-medium text-stone-600 underline">
          Спробуйте культивацію
        </Link>
      </div>
    );
  }

  const top = overview.active[0];
  const sleepHabitActive = overview.active.find((habit) => habit.kind === 'sleep');

  return (
    <section
      className="mb-4 rounded-2xl border border-gray-100 bg-white p-4 shadow-sm"
      data-testid="home-cultivation-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">Культивація · ранг</p>
          <p className="text-lg font-bold text-stone-900">{overview.rank?.name || '—'}</p>
        </div>
        {top && (
          <div className="min-w-0 flex-1 basis-56">
            <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-stone-800">
              {top.name} {(top.mode || top.today?.degraded) && <ModeBadge />}
            </p>
            <p className="text-xs text-gray-500">{top.today?.requirement || '—'}</p>
            <div className="mt-0.5">
              <DayStatusPill day={top.today?.day} />
            </div>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {sleepHabitActive && (
            <button
              type="button"
              onClick={() => setSleepHabit(sleepHabitActive)}
              className={`${BUTTON_PRIMARY} inline-flex items-center`}
            >
              <Moon size={14} className="mr-1.5" aria-hidden="true" /> Внести сон
            </button>
          )}
          <Link to="/practice" className="text-sm font-medium text-stone-600 underline hover:text-stone-900">
            Усі звички
          </Link>
        </div>
      </div>
      <SleepEntryModal
        habit={sleepHabit}
        timezone={overview.timezone}
        onClose={() => setSleepHabit(null)}
        onSaved={reload}
      />
    </section>
  );
}

export default HomeCultivationCard;
