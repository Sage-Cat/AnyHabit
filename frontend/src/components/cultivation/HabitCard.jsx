import { Moon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { DayStatusPill, ModeBadge, StageBadge, StatusStrip } from './common';
import { BUTTON_PRIMARY, BUTTON_SECONDARY, CARD_CLASS, formatDays, formatPercent } from './helpers';

function Metric({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-gray-400">{label}</dt>
      <dd className="text-sm font-semibold text-stone-800">{value}</dd>
    </div>
  );
}

/** Full card for an active habit. */
function HabitCard({ habit, onEnterSleep, onApplyRecommendation }) {
  const { today, recovery } = habit;
  const inMode = Boolean(habit.mode) || today?.degraded;

  return (
    <article className={CARD_CLASS} data-testid="habit-card" data-habit-id={habit.id}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link to={`/practice/${habit.id}`} className="text-lg font-bold text-stone-900 hover:underline">
            {habit.name}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <StageBadge stage={habit.stage} label={habit.stage_label} />
            {inMode && <ModeBadge />}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {habit.kind === 'sleep' && (
            <button type="button" onClick={() => onEnterSleep(habit)} className={BUTTON_PRIMARY}>
              <Moon size={14} className="mr-1.5 inline" aria-hidden="true" />
              Внести сон
            </button>
          )}
          {habit.kind !== 'sleep' && habit.tracker && (
            <Link to={`/tracker/${habit.tracker.id}`} className={BUTTON_SECONDARY}>
              Відкрити трекер
            </Link>
          )}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-[11px] uppercase tracking-wider text-gray-400">Сьогодні</p>
          <p className="mt-0.5 text-sm font-medium text-stone-800" data-testid="today-requirement">{today?.requirement || '—'}</p>
          {today?.minimum && <p className="text-xs text-gray-500">Мінімум: {today.minimum}</p>}
          <div className="mt-1.5"><DayStatusPill day={today?.day} /></div>
        </div>
        <div className="rounded-xl bg-stone-50 p-3">
          <p className="text-[11px] uppercase tracking-wider text-gray-400">Наступна підціль</p>
          {habit.next_subgoal ? (
            <p className="mt-0.5 text-sm text-stone-800">
              {habit.next_subgoal.name ? `${habit.next_subgoal.name}: ` : ''}
              {habit.next_subgoal.requirement}
            </p>
          ) : (
            <p className="mt-0.5 text-sm text-gray-400">—</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <StatusStrip days={habit.days} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Успіх за 30 днів" value={formatPercent(habit.success_rate_30)} />
        <Metric label="Поточне відхилення" value={recovery?.current_deviation ? `${recovery.current_deviation.ongoing_days ?? recovery.current_deviation.fail_days ?? '?'} дн.` : '—'} />
        <Metric label="До першого ОК (медіана)" value={formatDays(recovery?.first_ok_median)} />
        <Metric label="До підтвердження (медіана)" value={formatDays(recovery?.confirmed_median)} />
        <Metric label="У строк" value={formatPercent(recovery?.in_term_share)} />
      </dl>

      {habit.recommendation && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed border-sky-200 bg-sky-50/60 p-3">
          <p className="min-w-0 flex-1 text-sm text-sky-900">
            <span className="font-semibold">Пропозиція:</span> {habit.recommendation.reason}
          </p>
          <button type="button" onClick={() => onApplyRecommendation(habit)} className={BUTTON_SECONDARY}>
            Застосувати
          </button>
        </div>
      )}
    </article>
  );
}

export default HabitCard;
