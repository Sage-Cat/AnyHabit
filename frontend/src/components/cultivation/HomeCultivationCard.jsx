import { Check, Moon, Sprout } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { createBooleanLogApi } from '../../services/trackerApi';
import { useAppState } from '../../state/appState';
import RankEmblem from './RankEmblem';
import { Breakthrough, StageCounts, StageTimeline } from './RankStats';
import SleepEntryModal from './SleepEntryModal';
import { DayStatusPill, ModeBadge } from './common';
import { BUTTON_SECONDARY, useCultivationOverview } from './helpers';

const CARD = 'rounded-2xl border border-gray-100 bg-white p-4 shadow-sm';
const LABEL = 'text-[11px] font-semibold uppercase tracking-wider text-gray-400';

/** The cultivation rank: emblem, name, «Прорив» to the next one, habits per stage and the whole ladder. */
function HomeRankCard({ rank }) {
  if (!rank) return null;
  return (
    <section className={`${CARD} flex flex-col gap-3`} aria-label="Ранг культивації" data-testid="home-rank-card">
      <div className="flex items-center gap-4">
        <RankEmblem index={rank.index} size="lg" />
        <div className="min-w-0">
          <p className={LABEL}>Ранг культивації</p>
          <p className="text-xl font-bold text-stone-900" data-testid="home-rank-name">
            {rank.name}
          </p>
          {rank.peak_index > rank.index && rank.peak_name && (
            <p className="text-xs text-gray-500">Найвищий досягнутий: {rank.peak_name}</p>
          )}
        </div>
      </div>
      {rank.next ? (
        <p className="text-sm text-gray-600">
          <span className="font-medium text-stone-800">Далі — {rank.next.name}:</span> {rank.next.requirement}
        </p>
      ) : (
        <p className="text-sm text-gray-500">Це найвищий ранг у списку.</p>
      )}
      <Breakthrough next={rank.next} />
      <StageCounts stages={rank.stages} />
      <StageTimeline timeline={rank.timeline} height={96} />
      {rank.ladder?.length > 0 && (
        <ol className="flex flex-wrap items-center gap-1.5" aria-label="Шлях рангів">
          {rank.ladder.map((step) => (
            <li key={step.index} className={step.index > rank.index ? 'opacity-30' : ''}>
              <RankEmblem
                index={step.index}
                size="xs"
                label={step.name}
                className={step.index === rank.index ? 'ring-2 ring-stone-900 ring-offset-1' : ''}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** Every active habit with today's state and the one action it needs. */
function HomeTodayCard({ overview, onSleep, onChanged }) {
  const { notify } = useAppState();
  const [busyId, setBusyId] = useState(null);

  const markDone = async (habit) => {
    setBusyId(habit.id);
    try {
      await createBooleanLogApi(habit.tracker.id);
      notify.success(`«${habit.name}» — виконано`);
      await onChanged();
    } catch (error) {
      notify.error(error?.message || 'Не вдалося записати');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className={CARD} aria-label="Звички сьогодні" data-testid="home-today-card">
      <div className="flex items-center justify-between gap-3">
        <p className={LABEL}>Сьогодні</p>
        <Link to="/practice" className="text-sm font-medium text-stone-600 underline hover:text-stone-900">
          Усі звички
        </Link>
      </div>
      {overview.active.length === 0 ? (
        <p className="mt-2 text-sm text-gray-500">Активних звичок немає.</p>
      ) : (
        <ul className="mt-2 divide-y divide-gray-100">
          {overview.active.map((habit) => {
            const day = habit.today?.day;
            const done = day?.status === 'success';
            const requirement = habit.today?.requirement;
            return (
              <li
                key={habit.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5"
                data-testid="home-habit"
              >
                <div className="min-w-0 flex-1 basis-48">
                  <Link
                    to={`/practice/${habit.id}`}
                    className="flex flex-wrap items-center gap-2 text-sm font-medium text-stone-800 hover:underline"
                  >
                    {habit.name} {(habit.mode || habit.today?.degraded) && <ModeBadge />}
                  </Link>
                  {requirement && requirement !== 'виконати' && <p className="text-xs text-gray-500">{requirement}</p>}
                  {habit.today?.tolerance && (
                    <p className="text-xs text-amber-700">Допуск з попередженням: {habit.today.tolerance}</p>
                  )}
                  {day?.warning && (
                    <p className="text-xs text-amber-700" data-testid="home-habit-warning">
                      {day.warning}
                    </p>
                  )}
                </div>
                <DayStatusPill day={day} />
                {habit.kind === 'sleep' && (
                  <button
                    type="button"
                    onClick={() => onSleep(habit)}
                    className={`${BUTTON_SECONDARY} inline-flex items-center`}
                  >
                    <Moon size={14} className="mr-1.5" aria-hidden="true" /> Внести сон
                  </button>
                )}
                {habit.kind === 'boolean' && habit.tracker && !done && (
                  <button
                    type="button"
                    disabled={busyId === habit.id}
                    onClick={() => markDone(habit)}
                    className={`${BUTTON_SECONDARY} inline-flex items-center`}
                  >
                    <Check size={14} className="mr-1.5" aria-hidden="true" />
                    {busyId === habit.id ? 'Запис…' : 'Виконано'}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {overview.planned.length > 0 && (
        <p className="mt-2 text-xs text-gray-400">Заплановано: {overview.planned.map((h) => h.name).join(', ')}</p>
      )}
    </section>
  );
}

/**
 * Fixed block above the widget grid (not grid widgets): the rank card and
 * today's habits side by side. Stays quiet when the overview cannot be loaded,
 * so it never gets in the way of the home page.
 */
function HomeCultivationCard({ onChanged }) {
  const { overview, isLoading, error, reload: reloadOverview } = useCultivationOverview();
  const [sleepHabit, setSleepHabit] = useState(null);
  // Other home widgets read the same days, so they refresh together.
  const reload = async () => {
    await reloadOverview();
    onChanged?.();
  };

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

  return (
    <div className="mb-4 grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]" data-testid="home-cultivation-card">
      <HomeRankCard rank={overview.rank} />
      <HomeTodayCard overview={overview} onSleep={setSleepHabit} onChanged={reload} />
      <SleepEntryModal
        habit={sleepHabit}
        timezone={overview.timezone}
        onClose={() => setSleepHabit(null)}
        onSaved={reload}
      />
    </div>
  );
}

export default HomeCultivationCard;
