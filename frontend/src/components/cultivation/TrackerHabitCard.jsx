import { Sprout } from 'lucide-react';
import { Link } from 'react-router-dom';
import { LevelBadge, StageBadge } from './common';
import { BUTTON_SECONDARY, CARD_CLASS } from './helpers';

/**
 * What a cultivated habit asks for, on the page of the tracker that feeds it.
 * The tracker itself only knows its schedule, so without this the page says
 * nothing about the goal or the deadline. Stays empty for a plain tracker.
 */
function TrackerHabitCard({ habit, trackerDescription = '' }) {
  if (!habit) return null;
  const { requirement, tolerance, minimum } = habit.today || {};
  const rules = [
    ['Ціль', requirement && requirement !== 'виконати' ? requirement : null],
    ['Допуск з попередженням', tolerance],
    ['Мінімум', minimum]
  ].filter(([, value]) => value);

  return (
    <section className={`${CARD_CLASS} mx-4 mb-6 md:mx-10`} data-testid="tracker-habit-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <Sprout size={14} className="text-emerald-600" aria-hidden="true" /> Звичка культивації
            <StageBadge stage={habit.stage} label={habit.stage_label} />
            <LevelBadge ladder={habit.ladder} />
          </p>
          {/* The tracker's header already shows the description it was given from the passport. */}
          {habit.description && habit.description !== trackerDescription && (
            <p className="mt-2 text-sm text-stone-700">{habit.description}</p>
          )}
          {rules.length > 0 && (
            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
              {rules.map(([label, value]) => (
                <div key={label} className="flex gap-1.5">
                  <dt className="text-gray-500">{label}:</dt>
                  <dd className={label === 'Ціль' ? 'font-semibold text-stone-900' : 'text-stone-800'}>{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <Link to={`/practice/${habit.id}`} className={BUTTON_SECONDARY}>
          Паспорт і керування
        </Link>
      </div>
    </section>
  );
}

export default TrackerHabitCard;
