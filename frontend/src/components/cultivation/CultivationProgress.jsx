import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchProgressApi } from '../../services/cultivationApi';
import { formatChartDate } from '../../utils/labels';
import { pluralCount } from '../../utils/plural';
import { PausedBadge } from './common';
import { habitColorMap } from './habitColors';
import { CARD_CLASS, formatPercent } from './helpers';
import { DAY_MS, toIso, toTime } from './stageMeta';

const PERIODS = [
  { days: 30, label: '30 днів' },
  { days: 90, label: '90 днів' },
  { days: 365, label: 'Рік' }
];
// A gradient, so «Прорив» never shares a colour with a habit line.
const BREAKTHROUGH_GRADIENT = 'linear-gradient(90deg, #8b5cf6, #10b981)';
const TICK = { fontSize: 10, fill: '#9ca3af' };
const percentOf = (value) => (value == null ? null : Math.round(value * 100));

// A habit's path as one climbing scale: «Запланована», then per level Формування →
// Стабілізація → Інтегрована, the next level above the previous one. Between two
// marks the line rises with the readiness for the next stage, so moving on never
// looks like a fall.
const PATH_STAGES = ['formation', 'stabilization', 'integrated'];
const PATH_LABELS = { formation: 'Формування', stabilization: 'Стабілізація', integrated: 'Інтегрована' };
const PATH_STEP = PATH_STAGES.length;

/** Position on the path scale; null when the day has no stage. */
function pathPosition(point) {
  if (point.stage === 'planned') return 0;
  const step = PATH_STAGES.indexOf(point.stage);
  if (step < 0) return null;
  const level = Math.max(1, Number(point.level) || 1);
  const ready = point.stage === 'integrated' ? 0 : Math.min(1, Math.max(0, point.value ?? 0));
  return 1 + (level - 1) * PATH_STEP + step + ready;
}

/** The marks of the path scale up to the top of ``levels``. */
function pathTicks(levels) {
  const ticks = [{ value: 0, label: 'Запланована' }];
  for (let level = 1; level <= levels; level += 1) {
    PATH_STAGES.forEach((stage, step) => {
      ticks.push({
        value: 1 + (level - 1) * PATH_STEP + step,
        label: level > 1 ? `Р${level} · ${PATH_LABELS[stage]}` : PATH_LABELS[stage]
      });
    });
  }
  return ticks;
}

/** What a habit's point means: its stage, level and readiness for the next stage. */
function pathText(point) {
  if (!point) return '—';
  if (point.stage === 'planned') return 'Запланована';
  const parts = [PATH_LABELS[point.stage] || '—'];
  if (Number(point.level) > 1) parts.push(`рівень ${point.level}`);
  if (point.stage !== 'integrated' && point.value != null) parts.push(`готовність ${percentOf(point.value)}%`);
  return parts.join(' · ');
}
const shortDate = (time) => formatChartDate(toIso(time));

function Card({ title, hint, testId, className = '', children }) {
  return (
    <section className={`${CARD_CLASS} flex min-w-0 flex-col gap-3 ${className}`} data-testid={testId}>
      <div>
        <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
        {hint && <p className="mt-0.5 text-xs text-gray-500">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function dayTicks(first, last) {
  const step = Math.max(1, Math.ceil((last - first) / DAY_MS / 5)) * DAY_MS;
  const ticks = [];
  for (let time = first; time < last; time += step) ticks.push(time);
  ticks.push(last);
  return ticks;
}

/** «Прорив» per day with every habit's path through stages and levels; rank-ups as vertical lines. */
function BreakthroughHistory({ progress, colours }) {
  const { data, rankUps, ticks, levels } = useMemo(() => {
    const byDate = new Map(progress.days.map((day) => [day.date, { time: toTime(day.date), all: day.breakthrough }]));
    let top = 1;
    for (const habit of progress.habits) {
      for (const point of habit.readiness) {
        const row = byDate.get(point.date);
        if (!row) continue;
        row[`h${habit.id}`] = pathPosition(point);
        row[`p${habit.id}`] = point;
        if (point.stage && point.stage !== 'planned') top = Math.max(top, Number(point.level) || 1);
      }
    }
    const rows = [...byDate.values()];
    const ups = progress.days
      .filter((day, index) => index > 0 && day.rank_index > progress.days[index - 1].rank_index)
      .map((day) => ({ time: toTime(day.date), name: day.rank_name }));
    const middle = rows.length ? (rows[0].time + rows[rows.length - 1].time) / 2 : 0;
    for (const up of ups) up.late = up.time > middle; // label on the side with room
    return {
      data: rows,
      rankUps: ups,
      ticks: rows.length ? dayTicks(rows[0].time, rows[rows.length - 1].time) : [],
      levels: top
    };
  }, [progress]);
  const tracked = progress.habits.filter((habit) => habit.readiness.some((point) => pathPosition(point) != null));
  const marks = pathTicks(levels);
  const markLabel = Object.fromEntries(marks.map((mark) => [mark.value, mark.label]));

  return (
    <Card
      title="Прорив і готовність звичок"
      hint="Лінії звичок — етап і рівень, між позначками — готовність до наступного етапу; Прорив — шлях до наступного рангу (шкала справа)"
      testId="breakthrough-history"
      className="xl:col-span-2"
    >
      {data.length < 7 && <p className="text-xs text-amber-700">Даних поки мало: графік наповнюватиметься щодня.</p>}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 0, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="breakthrough-stroke" gradientUnits="userSpaceOnUse" x1="0%" y1="0" x2="100%" y2="0">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              ticks={ticks}
              tickFormatter={shortDate}
              tick={TICK}
            />
            <YAxis
              yAxisId="path"
              domain={[0, 1 + levels * PATH_STEP - 1]}
              ticks={marks.map((mark) => mark.value)}
              tickFormatter={(value) => markLabel[value] ?? ''}
              tick={TICK}
              width={levels > 1 ? 130 : 84}
              allowDecimals
            />
            <YAxis
              yAxisId="pct"
              orientation="right"
              domain={[0, 100]}
              ticks={[0, 50, 100]}
              unit="%"
              tick={TICK}
              width={40}
            />
            <Tooltip
              labelFormatter={shortDate}
              formatter={(value, name, item) => {
                if (item.dataKey === 'all') return [value == null ? '—' : `${value}%`, name];
                return [pathText(item.payload[String(item.dataKey).replace(/^h/, 'p')]), name];
              }}
            />
            {rankUps.map((up) => (
              <ReferenceLine
                key={up.time}
                yAxisId="path"
                x={up.time}
                stroke="#f59e0b"
                strokeDasharray="4 3"
                label={{
                  value: up.name,
                  position: up.late ? 'insideTopRight' : 'insideTopLeft',
                  fontSize: 10,
                  fill: '#b45309'
                }}
              />
            ))}
            {tracked.map((habit) => (
              <Line
                key={habit.id}
                yAxisId="path"
                type="monotone"
                dataKey={`h${habit.id}`}
                name={habit.name}
                stroke={colours[habit.id]}
                strokeWidth={1.5}
                dot={data.length < 3}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            <Line
              yAxisId="pct"
              type="stepAfter"
              dataKey="all"
              name="Прорив"
              stroke="url(#breakthrough-stroke)"
              strokeWidth={3}
              dot={data.length < 3}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-700">
        <li className="flex items-center gap-1.5">
          <span className="h-1 w-4 rounded-full" style={{ background: BREAKTHROUGH_GRADIENT }} /> Прорив
        </li>
        {tracked.map((habit) => (
          <li key={habit.id} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ backgroundColor: colours[habit.id] }} /> {habit.name}
          </li>
        ))}
        {rankUps.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span className="h-3 border-l-2 border-dashed" style={{ borderColor: '#f59e0b' }} /> новий ранг
          </li>
        )}
      </ul>
    </Card>
  );
}

function ReadinessDetails({ progress }) {
  const rate = progress.success_rate == null ? '—' : formatPercent(progress.success_rate);
  return (
    <>
      <p className="text-xs text-gray-500">
        Днів з оцінкою {progress.observed_days} з {progress.need_days} за {progress.window_days} дн. · успіх {rate}{' '}
        (поріг {formatPercent(progress.need_rate)})
      </p>
      {progress.readiness >= 1 ? (
        <p className="text-xs font-medium text-emerald-700">
          Готово: перехід пропонується на сторінці звички, у розділі «Керування»
        </p>
      ) : (
        progress.blockers.length > 0 && (
          <ul className="list-inside list-disc text-xs text-gray-500">
            {progress.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        )
      )}
    </>
  );
}

/** Where each habit stands now on its way to the next stage, and what still holds it back. */
function ReadinessNow({ habits, colours }) {
  return (
    <Card title="Готовність до наступного етапу" hint="Станом на сьогодні" testId="readiness-now">
      <ul className="space-y-4">
        {habits.map((habit) => {
          const progress = habit.progress;
          const percent = progress ? Math.floor(progress.readiness * 100) : null;
          return (
            <li key={habit.id} className="space-y-1.5" data-testid="readiness-row">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="flex items-center gap-2">
                  <Link to={`/practice/${habit.id}`} className="font-medium text-stone-800 hover:underline">
                    {habit.name}
                  </Link>
                  {habit.paused && <PausedBadge />}
                </span>
                <span className="text-xs text-gray-500">
                  {habit.stage_label}
                  {progress && ` → ${progress.target_label}`}
                  {percent != null && <span className="ml-2 text-sm font-semibold text-stone-900">{percent}%</span>}
                </span>
              </div>
              {progress ? (
                <>
                  <div className="h-2 overflow-hidden rounded-full bg-stone-100">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${percent}%`, backgroundColor: colours[habit.id] }}
                    />
                  </div>
                  <ReadinessDetails progress={progress} />
                </>
              ) : (
                <p className="text-xs text-gray-500">
                  {habit.stage === 'integrated'
                    ? `Утримується ${pluralCount(habit.held_days, ['день', 'дні', 'днів'])} без перерви`
                    : 'Ще не розпочата'}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

/** Charts that follow cultivation itself: «Прорив» and stage readiness. */
function CultivationProgress({ refreshKey }) {
  const [days, setDays] = useState(90);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetchProgressApi(days)
      .then((response) => {
        if (!cancelled) {
          setProgress(response);
          setError('');
        }
      })
      .catch((reason) => {
        if (!cancelled) setError(reason.message || 'Не вдалося завантажити прогрес');
      });
    return () => {
      cancelled = true;
    };
  }, [days, refreshKey]);

  const colours = useMemo(() => habitColorMap(progress?.habits || []), [progress]);

  return (
    <section className="space-y-4" aria-label="Прогрес культивації" data-testid="cultivation-progress">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-stone-900">Прогрес культивації</h2>
        <div className="flex gap-1 rounded-xl bg-stone-100 p-1" role="group" aria-label="Період">
          {PERIODS.map((period) => (
            <button
              key={period.days}
              type="button"
              onClick={() => setDays(period.days)}
              aria-pressed={days === period.days}
              className={`rounded-lg px-3 py-1 text-xs font-medium ${
                days === period.days ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500 hover:text-stone-800'
              }`}
            >
              {period.label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <p className="rounded-xl border border-rose-100 bg-white p-4 text-sm text-rose-600" role="alert">
          {error}
        </p>
      )}
      {!progress && !error && <p className="text-sm text-gray-500">Завантаження…</p>}
      {progress && progress.habits.length > 0 && (
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <BreakthroughHistory progress={progress} colours={colours} />
          <ReadinessNow habits={progress.habits} colours={colours} />
        </div>
      )}
    </section>
  );
}

export default CultivationProgress;
