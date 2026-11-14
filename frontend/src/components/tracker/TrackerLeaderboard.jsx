import { Flame, Medal, Users } from 'lucide-react';
import { formatRelative } from '../../utils/date';
import { formatNumber } from '../../utils/number';

function TrackerLeaderboard({ shareStats }) {
  if (!shareStats || !shareStats.leaderboard?.length) return null;

  return (
    <section className="mb-8 rounded-3xl border border-gray-100 bg-white p-5 shadow-sm md:p-6">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-stone-700">
            <Users size={16} /> Спільний прогрес
          </h2>
          <p className="mt-1 text-xs text-gray-400">Усі учасники цієї звички.</p>
        </div>

        {shareStats.groupStreakStats && (
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-700">
            <div className="flex items-center gap-2 font-semibold text-stone-900">
              <Flame size={16} /> Серія групи: {shareStats.groupStreakStats.current}{' '}
              <span className="font-normal text-stone-500">{shareStats.groupStreakStats.periodLabel}</span>
            </div>
            <div className="mt-1 text-xs text-stone-500">Зараховується, лише коли всі виконали період.</div>
          </div>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {shareStats.leaderboard.map((entry, index) => (
          <article key={entry.user.id} className="rounded-3xl border border-gray-100 bg-stone-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-stone-900">
                  <Medal size={16} className={index === 0 ? 'text-amber-500' : 'text-stone-400'} />
                  <span className="truncate">{entry.user.username}</span>
                </h3>
                <p className="mt-1 text-xs text-stone-500">Остання активність: {formatRelative(entry.lastActivityAt)}</p>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-2xl font-semibold text-stone-900">{entry.streakStats.current}</div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-stone-400">
                  {entry.streakStats.periodLabel}
                </div>
              </div>
            </div>

            <dl className="mt-4 space-y-3 text-sm text-stone-600">
              <div className="flex items-center justify-between rounded-2xl bg-white px-3 py-2">
                <dt>Прогрес</dt>
                <dd className="font-medium text-stone-900">{formatNumber(entry.dailyProgress.percentage, 0)}%</dd>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-white px-3 py-2">
                <dt>Виконано</dt>
                <dd className="font-medium text-stone-900">
                  {formatNumber(entry.dailyProgress.total)} / {formatNumber(entry.dailyProgress.target)}
                </dd>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-white px-3 py-2">
                <dt>Найдовша серія</dt>
                <dd className="font-medium text-stone-900">{entry.streakStats.longest}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

export default TrackerLeaderboard;
