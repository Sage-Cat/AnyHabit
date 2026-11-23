import { Menu, Plus, Sprout } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppState } from '../../state/appState';
import CultivationProgress from './CultivationProgress';
import NewHabitModal from './NewHabitModal';
import RankCard from './RankCard';
import { DayStatusPill, LevelBadge, PausedBadge, StageBadge } from './common';
import { BUTTON_PRIMARY, CARD_CLASS, formatPercent, useCultivationOverview } from './helpers';

function CompactList({ title, habits, testId }) {
  if (!habits?.length) return null;
  return (
    <section data-testid={testId}>
      <h3 className="mb-2 text-sm font-semibold text-stone-700">{title}</h3>
      <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-100 bg-white">
        {habits.map((habit) => (
          <li key={habit.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
            <Link to={`/practice/${habit.id}`} className="font-medium text-stone-800 hover:underline">
              {habit.name}
            </Link>
            <span className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
              {habit.today?.requirement && <span>{habit.today.requirement}</span>}
              {habit.stage === 'integrated' && <span>Успіх за 30 днів: {formatPercent(habit.success_rate_30)}</span>}
              {habit.stage === 'integrated' && <DayStatusPill day={habit.today?.day} />}
              <StageBadge stage={habit.stage} label={habit.stage_label} />
              <LevelBadge ladder={habit.ladder} />
              {habit.paused && <PausedBadge />}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PracticePage() {
  const { setIsSidebarOpen } = useAppState();
  const { overview, error, isLoading, reload } = useCultivationOverview();
  const [isNewOpen, setIsNewOpen] = useState(false);

  useEffect(() => {
    document.title = 'Культивація — AnyHabit';
  }, []);

  const total = overview ? overview.active.length + overview.integrated.length + overview.planned.length : 0;

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#fcfcfc]">
      <div className="border-b border-gray-100 bg-white/80 px-4 pb-5 pt-6 backdrop-blur-sm md:px-10 md:pt-10">
        <div className="mx-auto flex w-full max-w-screen-2xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsSidebarOpen(true)}
              className="text-stone-500 hover:text-stone-900 md:hidden"
              aria-label="Відкрити навігацію"
            >
              <Menu size={24} />
            </button>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-stone-900 md:text-3xl">Культивація</h1>
              <p className="mt-1 text-sm text-gray-500">Вирощування звичок за етапами: від формування до інтеграції.</p>
            </div>
          </div>
          <button
            type="button"
            id="new-practice-habit"
            onClick={() => setIsNewOpen(true)}
            className={`${BUTTON_PRIMARY} inline-flex items-center gap-2`}
          >
            <Plus size={16} /> Нова звичка
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10">
        <div className="mx-auto w-full max-w-screen-2xl space-y-5" data-testid="practice-content">
          {isLoading && <div className={`${CARD_CLASS} text-center text-gray-500`}>Завантаження…</div>}
          {!isLoading && error && (
            <div className="rounded-2xl border border-rose-100 bg-white p-6 text-rose-600" role="alert">
              {error}
            </div>
          )}

          {overview && (
            <>
              {overview.warnings?.length > 0 && (
                <section className="space-y-2" aria-label="Попередження" data-testid="overview-warnings">
                  {overview.warnings.map((warning) => {
                    const habit = [...overview.active, ...overview.integrated, ...overview.planned].find(
                      (item) => item.id === warning.habit_id
                    );
                    return (
                      <div
                        key={`${warning.habit_id}-${warning.message}`}
                        className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                      >
                        {habit && (
                          <Link to={`/practice/${habit.id}`} className="mr-1 font-semibold underline">
                            {habit.name}:
                          </Link>
                        )}
                        {warning.message}
                      </div>
                    );
                  })}
                </section>
              )}

              <RankCard rank={overview.rank} />

              {total === 0 && (
                <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-8 text-center text-gray-500">
                  <Sprout className="mx-auto mb-2 text-emerald-600" size={28} />
                  <p className="font-semibold text-stone-800">Поки що немає жодної звички для культивації</p>
                  <p className="mt-1 text-sm">Додайте першу, наприклад режим сну.</p>
                </div>
              )}

              {total > 0 && <CultivationProgress refreshKey={overview} />}

              <CompactList title="Інтегровані" habits={overview.integrated} testId="integrated-habits" />
              <CompactList title="Заплановані" habits={overview.planned} testId="planned-habits" />
            </>
          )}
        </div>
      </div>

      <NewHabitModal isOpen={isNewOpen} onClose={() => setIsNewOpen(false)} onCreated={reload} />
    </div>
  );
}

export default PracticePage;
