import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { fetchProgressApi } from '../../services/cultivationApi';
import { formatChartDate } from '../../utils/labels';
import { pluralCount } from '../../utils/plural';
import { habitColorMap } from './habitColors';
import { CARD_CLASS, formatPercent } from './helpers';
import { DAY_MS, STAGE_COLOUR, STAGE_META, toIso, toTime } from './stageMeta';

const PERIODS = [
  { days: 30, label: '30 днів' },
  { days: 90, label: '90 днів' },
  { days: 365, label: 'Рік' }
];
// A gradient, so «Прорив» never shares a colour with a habit line.
const BREAKTHROUGH_GRADIENT = 'linear-gradient(90deg, #8b5cf6, #10b981)';
const TICK = { fontSize: 10, fill: '#9ca3af' };
const percentOf = (value) => (value == null ? null : Math.round(value * 100));
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

/** «Прорив» per day with every habit's readiness for its next stage; rank-ups as vertical lines. */
function BreakthroughHistory({ progress, colours }) {
  const { data, rankUps, ticks } = useMemo(() => {
    const byDate = new Map(progress.days.map((day) => [day.date, { time: toTime(day.date), all: day.breakthrough }]));
    for (const habit of progress.habits) {
      for (const point of habit.readiness) {
        const row = byDate.get(point.date);
        if (row) row[`h${habit.id}`] = percentOf(point.value);
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
      ticks: rows.length ? dayTicks(rows[0].time, rows[rows.length - 1].time) : []
    };
  }, [progress]);
  const tracked = progress.habits.filter((habit) => habit.readiness.some((point) => point.value != null));

  return (
    <Card
      title="Прорив і готовність звичок"
      hint="Прорив — шлях до наступного рангу; лінії звичок — готовність до наступного етапу"
      testId="breakthrough-history"
      className="xl:col-span-2"
    >
      {data.length < 7 && <p className="text-xs text-amber-700">Даних поки мало: графік наповнюватиметься щодня.</p>}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
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
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" tick={TICK} />
            <Tooltip
              labelFormatter={shortDate}
              formatter={(value, name) => [value == null ? '—' : `${value}%`, name]}
            />
            {rankUps.map((up) => (
              <ReferenceLine
                key={up.time}
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
                <Link to={`/practice/${habit.id}`} className="font-medium text-stone-800 hover:underline">
                  {habit.name}
                </Link>
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

/** Each habit's stages over the period as one coloured bar. */
function StagePaths({ progress }) {
  const first = toTime(progress.since);
  const last = toTime(progress.until);
  const span = (last - first) / DAY_MS + 1;
  const used = new Set(progress.habits.flatMap((habit) => habit.segments.map((segment) => segment.stage)));

  return (
    <Card title="Шлях звичок за етапами" hint="Скільки днів кожна звичка провела на кожному етапі" testId="stage-paths">
      <ul className="space-y-3">
        {progress.habits.map((habit) => (
          <li key={habit.id}>
            <p className="mb-1 truncate text-xs font-medium text-stone-700">{habit.name}</p>
            <div className="relative h-4 overflow-hidden rounded-md bg-stone-100" data-testid="stage-path">
              {habit.segments.map((segment) => {
                const start = (toTime(segment.start) - first) / DAY_MS;
                const length = (toTime(segment.end) - toTime(segment.start)) / DAY_MS + 1;
                return (
                  <span
                    key={segment.start}
                    className="absolute inset-y-0"
                    title={`${segment.stage ? STAGE_META.find((s) => s.key === segment.stage)?.label : ''}: ${shortDate(toTime(segment.start))} — ${shortDate(toTime(segment.end))}, ${pluralCount(length, ['день', 'дні', 'днів'])}`}
                    style={{
                      left: `${(start / span) * 100}%`,
                      width: `${(length / span) * 100}%`,
                      backgroundColor: STAGE_COLOUR[segment.stage] || '#d6d3d1'
                    }}
                  />
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      <div className="flex justify-between text-[10px] text-gray-400">
        <span>{shortDate(first)}</span>
        <span>{shortDate(last)}</span>
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-500">
        {STAGE_META.filter((stage) => used.has(stage.key)).map((stage) => (
          <li key={stage.key} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: stage.colour }} /> {stage.label}
          </li>
        ))}
      </ul>
    </Card>
  );
}

const monthLabel = (key) =>
  new Date(`${key}-01T00:00:00Z`).toLocaleDateString('uk-UA', { month: 'short', year: '2-digit', timeZone: 'UTC' });

/** Deviations of all habits per month and how fast the first good day came after them. */
function Deviations({ deviations }) {
  const firstActive = deviations.findIndex((month) => month.deviations > 0);
  const shown = deviations.slice(firstActive < 0 ? -3 : Math.min(firstActive, deviations.length - 3));
  const total = shown.reduce((sum, month) => sum + month.deviations, 0);
  const data = shown.map((month) => ({ ...month, label: monthLabel(month.month) }));

  return (
    <Card
      title="Збої та повернення"
      hint="Збої всіх звичок за місяцями і медіана днів до першого успішного дня"
      testId="deviations-chart"
    >
      {total === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">Збоїв ще не було.</p>
      ) : (
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="label" tick={TICK} />
              <YAxis yAxisId="count" allowDecimals={false} tick={TICK} />
              <YAxis yAxisId="days" orientation="right" allowDecimals={false} unit=" дн." tick={TICK} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="count" dataKey="deviations" name="Збоїв" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              <Line
                yAxisId="days"
                type="monotone"
                dataKey="first_ok_median"
                name="Днів до першого успіху (медіана)"
                stroke="#0ea5e9"
                strokeWidth={2}
                connectNulls
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

/** Charts that follow cultivation itself: «Прорив», stage readiness, stage paths and recovery. */
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
          <div className="grid min-w-0 gap-4">
            <StagePaths progress={progress} />
            <Deviations deviations={progress.deviations} />
          </div>
        </div>
      )}
    </section>
  );
}

export default CultivationProgress;
