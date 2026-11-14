import { Activity, CheckCircle2, Coins, Flame, Percent, TrendingUp } from 'lucide-react';
import { formatNumber } from '../../utils/number';
import { PERIOD_NOUNS } from '../../constants/tracker';
import { formatWindowLabel } from '../../utils/tracker';


const cardClass = 'rounded-3xl border border-gray-100 bg-white p-6 shadow-sm';
const cardHeadingClass = 'mb-2 flex items-center gap-2 text-sm font-medium text-gray-500';

function TrackerStats({ selectedTracker, dailyProgress, currentMath, streakStats, consistency, shareStats }) {
  const isQuit = selectedTracker.type === 'quit';
  const isBoolean = selectedTracker.type === 'boolean';
  const hasImpact = selectedTracker.impact_amount > 0 && !isBoolean;

  // Only meaningful once a relapse has actually split the two figures.
  const showsLifetime = isQuit && currentMath.lifetimeMainUnit !== currentMath.mainUnit;

  return (
    <div className="flex flex-col px-4 pb-10 md:px-10">
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className={cardClass}>
          <div className={cardHeadingClass}>
            {isQuit ? <TrendingUp size={16} /> : <Activity size={16} />}
            {isQuit ? 'Утримано' : 'Виконано'}
          </div>

          {isBoolean ? (
            <div className="mt-4 flex items-center gap-3">
              {dailyProgress.total >= dailyProgress.target ? (
                <div className="flex items-center gap-2 text-lg font-medium text-emerald-500">
                  <CheckCircle2 size={24} /> Виконано за {formatWindowLabel(selectedTracker)}!
                </div>
              ) : (
                <div className="text-lg font-medium text-gray-400">Ще не виконано</div>
              )}
            </div>
          ) : (
            <>
              <div className="flex items-end gap-2">
                <div className="text-4xl font-semibold tracking-tight">{currentMath.mainUnit}</div>
                <div className="mb-1 text-lg text-gray-400">{selectedTracker.unit}</div>
              </div>

              {showsLifetime && (
                <p className="mt-2 text-xs text-gray-400">
                  {currentMath.lifetimeMainUnit} {selectedTracker.unit} від самого початку
                </p>
              )}

              {selectedTracker.type === 'build' && (
                <div className="mt-6">
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="font-medium text-stone-600">Прогрес за {formatWindowLabel(selectedTracker)}</span>
                    <span className="text-stone-400">
                      {formatNumber(dailyProgress.total)} / {formatNumber(dailyProgress.target)}
                    </span>
                  </div>
                  <div
                    className="h-2 w-full overflow-hidden rounded-full bg-stone-100"
                    role="progressbar"
                    aria-valuenow={Math.round(dailyProgress.percentage)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Прогрес за поточний період"
                  >
                    <div
                      className="h-full bg-stone-900 transition-all duration-500 ease-out"
                      style={{ width: `${Math.min(100, dailyProgress.percentage)}%` }}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className={`${cardClass} flex flex-col justify-between`}>
          <div className={cardHeadingClass}>
            <Flame size={16} />
            Серії
          </div>
          <div className={`mt-3 grid gap-4 ${shareStats?.groupStreakStats ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <div className="rounded-2xl border border-gray-100 bg-stone-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Поточна</div>
              <div className="mt-1 text-3xl font-semibold text-stone-900">{streakStats.current}</div>
              <div className="mt-1 text-xs text-gray-500">{streakStats.periodLabel}</div>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-stone-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Найдовша</div>
              <div className="mt-1 text-3xl font-semibold text-stone-900">{streakStats.longest}</div>
              <div className="mt-1 text-xs text-gray-500">{streakStats.periodLabel}</div>
            </div>
            {shareStats?.groupStreakStats && (
              <div className="rounded-2xl border border-gray-100 bg-stone-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Група</div>
                <div className="mt-1 text-3xl font-semibold text-stone-900">
                  {shareStats.groupStreakStats.current}
                </div>
                <div className="mt-1 text-xs text-gray-500">{shareStats.groupStreakStats.periodLabel}</div>
              </div>
            )}
          </div>

          {isQuit && streakStats.totalRelapses > 0 && (
            <p className="mt-3 text-xs text-gray-400">
              Зривів записано: {streakStats.totalRelapses}. Почати знову — теж прогрес.
            </p>
          )}
        </div>

        {/* A streak says nothing about the nine times you missed. This does. */}
        {consistency?.totalPeriods > 0 && (
          <div className={`${cardClass} flex flex-col justify-between`}>
            <div className={cardHeadingClass}>
              <Percent size={16} />
              Регулярність
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div className="rounded-2xl border border-gray-100 bg-stone-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">За весь час</div>
                <div className="mt-1 text-3xl font-semibold text-stone-900">{consistency.rate}%</div>
                <div className="mt-1 text-xs text-gray-500">
                  {consistency.completedPeriods} із {consistency.totalPeriods}
                </div>
              </div>
              <div className="rounded-2xl border border-gray-100 bg-stone-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">Нещодавно</div>
                <div className="mt-1 text-3xl font-semibold text-stone-900">{consistency.recentRate}%</div>
                <div className="mt-1 text-xs text-gray-500">останні {consistency.recentWindow}</div>
              </div>
            </div>
          </div>
        )}

        {hasImpact && (
          <div className={`${cardClass} flex flex-col justify-between`}>
            <div>
              <div className={cardHeadingClass}>
                <Coins size={16} />
                {isQuit ? 'Заощаджено' : 'Вплив'}
              </div>
              <div className="text-4xl font-semibold tracking-tight">
                {currentMath.impactValue} {selectedTracker.impact_unit || '$'}
              </div>
              {showsLifetime && (
                <p className="mt-2 text-xs text-gray-400">
                  {currentMath.lifetimeImpactValue} {selectedTracker.impact_unit || '$'} від самого початку
                </p>
              )}
            </div>
            <div className="mt-4 text-sm text-gray-400">
              Вплив: {selectedTracker.impact_amount} {selectedTracker.impact_unit || '$'} /{' '}
              {PERIOD_NOUNS[selectedTracker.impact_per] || selectedTracker.impact_per}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TrackerStats;
