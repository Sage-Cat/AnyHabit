import { Sprout } from 'lucide-react';
import { Link } from 'react-router-dom';
import RankEmblem from './RankEmblem';
import { Breakthrough, StageCounts, StageTimeline } from './RankStats';
import { useCultivationOverview } from './helpers';

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

/**
 * Fixed block above the widget grid (not a grid widget): the rank card. Stays
 * quiet when the overview cannot be loaded, so it never gets in the way of the home page.
 */
function HomeCultivationCard() {
  const { overview, isLoading, error } = useCultivationOverview();

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
    <div className="mb-4" data-testid="home-cultivation-card">
      <HomeRankCard rank={overview.rank} />
    </div>
  );
}

export default HomeCultivationCard;
