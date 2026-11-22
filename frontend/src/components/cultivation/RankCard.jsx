import { Check, ChevronDown, Circle } from 'lucide-react';
import { useState } from 'react';
import { CARD_CLASS, formatDay } from './helpers';
import RankEmblem from './RankEmblem';
import { Breakthrough, StageCounts, StageTimeline } from './RankStats';

function RankCard({ rank }) {
  const [showLadder, setShowLadder] = useState(false);
  if (!rank) return null;

  const peakHigher = rank.peak_index > rank.index && rank.peak_name;
  const habitsCounted = (rank.habits || []).filter((habit) => habit.counted);

  return (
    <section className={CARD_CLASS} aria-label="Ранг" data-testid="rank-card">
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="min-w-0">
          <div className="flex items-center gap-4">
            <RankEmblem index={rank.index} size="lg" />
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Ранг</p>
              <h2 className="mt-1 text-3xl font-bold tracking-tight text-stone-900" data-testid="rank-name">
                {rank.name}
              </h2>
            </div>
          </div>
          {peakHigher && <p className="mt-1 text-sm text-gray-500">Найвищий досягнутий: {rank.peak_name}</p>}

          {rank.next && (
            <div className="mt-4 rounded-xl bg-stone-50 p-4">
              <Breakthrough next={rank.next} />
              <p className="mt-3 text-sm font-semibold text-stone-800">Далі: {rank.next.name}</p>
              {rank.next.requirement && <p className="mt-1 text-sm text-gray-600">{rank.next.requirement}</p>}
              {rank.next.confirmed === false && (
                <p className="mt-1 text-xs text-amber-700">Умова — пропозиція, ще не підтверджена вами</p>
              )}
              {rank.next.progress?.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {rank.next.progress.map((item) => (
                    <li key={item.label} className="flex items-start gap-2 text-sm">
                      {item.done ? (
                        <Check size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-label="виконано" />
                      ) : (
                        <Circle size={16} className="mt-0.5 shrink-0 text-gray-300" aria-label="не виконано" />
                      )}
                      <span className={item.done ? 'text-stone-700' : 'text-gray-600'}>
                        {item.label}
                        {item.have != null && item.need != null && (
                          <span className="ml-1 text-gray-400">
                            ({item.have} з {item.need})
                          </span>
                        )}
                        {item.fraction != null && !item.done && (
                          <span className="ml-1 text-gray-400">· {Math.floor(item.fraction * 100)}%</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {!rank.next && <p className="mt-3 text-sm text-gray-500">Це найвищий ранг у списку.</p>}

          {rank.warnings?.length > 0 && (
            <ul className="mt-3 space-y-1">
              {rank.warnings.map((warning) => (
                <li key={warning} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {warning}
                </li>
              ))}
            </ul>
          )}

          {habitsCounted.length > 0 && (
            <p className="mt-3 text-xs text-gray-400">
              У рахунок ранга йдуть:{' '}
              {habitsCounted
                .map((habit) => {
                  const credit = habit.credit ?? habit.level;
                  return credit > 1 ? `${habit.name} (рівень ${credit})` : habit.name;
                })
                .join(', ')}
            </p>
          )}
        </div>

        <div className="min-w-0 space-y-4" data-testid="rank-stage-stats">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Звички за етапами</p>
          <StageCounts stages={rank.stages} />
          <StageTimeline timeline={rank.timeline} height={160} />
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowLadder((open) => !open)}
        aria-expanded={showLadder}
        className="mt-4 flex items-center gap-1 text-sm font-medium text-stone-600 hover:text-stone-900"
      >
        <ChevronDown size={16} className={`transition-transform ${showLadder ? '' : '-rotate-90'}`} />
        Усі ранги
      </button>
      {showLadder && (
        <ol className="mt-2 space-y-1" data-testid="rank-ladder">
          {(rank.ladder || []).map((step) => (
            <li
              key={step.index}
              className={`flex items-start gap-3 rounded-lg px-3 py-2 text-sm ${
                step.index === rank.index ? 'bg-stone-900 text-white' : 'bg-stone-50 text-stone-700'
              }`}
            >
              <RankEmblem index={step.index} size="sm" className={step.index > rank.index ? 'opacity-40' : ''} />
              <span className="min-w-0">
                <span className="font-medium">{step.name}</span>
                {step.confirmed === false && (
                  <span
                    className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-medium ${step.index === rank.index ? 'bg-white/20' : 'bg-amber-100 text-amber-800'}`}
                  >
                    пропозиція
                  </span>
                )}
                {step.requirement && (
                  <span className={`block text-xs ${step.index === rank.index ? 'text-stone-300' : 'text-gray-500'}`}>
                    {step.requirement}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>
      )}

      {rank.history?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Історія рангів</p>
          <ul className="mt-2 space-y-1 text-sm text-gray-600">
            {rank.history.map((entry) => (
              <li key={`${entry.date}-${entry.to_name}`}>
                {formatDay(entry.date, { day: 'numeric', month: 'short', year: 'numeric' })}: {entry.from_name || '—'} →{' '}
                {entry.to_name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default RankCard;
