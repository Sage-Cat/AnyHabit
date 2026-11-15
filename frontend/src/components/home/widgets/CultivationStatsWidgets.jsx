import { useMemo } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatChartDate } from '../../../utils/labels';
import { pluralCount } from '../../../utils/plural';
import { habitColorMap } from '../../cultivation/habitColors';
import { formatDay, formatPercent } from '../../cultivation/helpers';
import { weekColumns } from '../../../utils/heatmap';
import HeatmapGrid from '../../ui/HeatmapGrid';
import { CHART_DAY_OPTIONS } from './helpers';
import { WidgetEmptyState, WidgetLoading } from './shared';

// Inline colours: the dark theme repaints the matching Tailwind classes.
const STATUS_BAR = [
  { key: 'success', label: 'Успіх', colour: '#10b981' },
  { key: 'minimum', label: 'Мінімум', colour: '#a3e635' },
  { key: 'fail', label: 'Порушення', colour: '#f43f5e' },
  { key: 'exception', label: 'Виняток', colour: '#7dd3fc' },
  { key: 'no_data', label: 'Немає даних', colour: '#a8a29e' }
];

const SHADES = [
  { test: (rate) => rate >= 1, colour: '#10b981', label: 'усе виконано' },
  { test: (rate) => rate >= 0.5, colour: '#a3e635', label: 'більшість' },
  { test: (rate) => rate > 0, colour: '#fb923c', label: 'менше половини' },
  { test: () => true, colour: '#f43f5e', label: 'нічого' }
];

function Gate({ stats, isLoading, children }) {
  if (isLoading && !stats) return <WidgetLoading />;
  if (!stats) return <WidgetEmptyState title="Статистика недоступна" hint="Спробуйте оновити сторінку." />;
  if (!stats.habits?.length) {
    return (
      <WidgetEmptyState title="Звичок у культивації ще немає" hint="Тут з'явиться статистика всіх звичок разом." />
    );
  }
  return children;
}

function Tile({ label, value, hint, testId }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-stone-50 p-3" data-testid={testId}>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-stone-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

/** Totals across every habit: today, 7 and 30 days, the run without failures and warnings. */
export function OverallStatsWidget({ stats, isLoading }) {
  return (
    <Gate stats={stats} isLoading={isLoading}>
      <OverallStats summary={stats?.summary} />
    </Gate>
  );
}

function OverallStats({ summary }) {
  const today = summary.today;
  const week = summary.rates['7'];
  const month = summary.rates['30'];
  const total = STATUS_BAR.reduce((sum, item) => sum + (month.counts[item.key] || 0), 0);

  return (
    <div className="flex h-full flex-col gap-4" data-testid="overall-stats">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] gap-3">
        <Tile
          label="Сьогодні"
          value={`${today.counts.success} / ${summary.habits}`}
          hint={today.pending ? `ще без запису: ${today.pending}` : 'усе внесено'}
          testId="stats-today"
        />
        <Tile
          label="7 днів"
          value={formatPercent(week.success_rate)}
          hint={`з мінімумом ${formatPercent(week.acceptable_rate)} · оцінено ${week.judged}`}
          testId="stats-week"
        />
        <Tile
          label="30 днів"
          value={formatPercent(month.success_rate)}
          hint={`з мінімумом ${formatPercent(month.acceptable_rate)} · оцінено ${month.judged}`}
        />
        <Tile
          label="Без порушень"
          value={pluralCount(summary.clean_streak, ['день', 'дні', 'днів'])}
          hint={`найдовше: ${summary.best_clean_streak}`}
          testId="stats-streak"
        />
        <Tile
          label="Попередження"
          value={month.warnings}
          hint="днів у межах допуску за 30 днів"
          testId="stats-warnings"
        />
      </div>

      {total > 0 && (
        <div>
          <p className="mb-1.5 text-xs text-gray-500">Дні всіх звичок за 30 днів</p>
          <div className="flex h-2.5 overflow-hidden rounded-full" role="img" aria-label="Розподіл днів за статусами">
            {STATUS_BAR.filter((item) => month.counts[item.key]).map((item) => (
              <span
                key={item.key}
                style={{ width: `${(month.counts[item.key] / total) * 100}%`, backgroundColor: item.colour }}
              />
            ))}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
            {STATUS_BAR.map((item) => (
              <li key={item.key} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.colour }} />
                {item.label}: {month.counts[item.key] || 0}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const toPercent = (value) => (value === null || value === undefined ? null : Math.round(value * 1000) / 10);

/** One line per habit (its own colour) plus all habits together: share of successful days over 7 days. */
export function HabitsChartWidget({ stats, isLoading, config }) {
  return (
    <Gate stats={stats} isLoading={isLoading}>
      <HabitsChart stats={stats} days={CHART_DAY_OPTIONS.includes(config?.days) ? config.days : 30} />
    </Gate>
  );
}

function HabitsChart({ stats, days }) {
  const colours = useMemo(() => habitColorMap(stats.habits), [stats.habits]);
  const data = useMemo(() => {
    const offset = Math.max(0, stats.daily.length - days);
    return stats.daily.slice(offset).map((day, index) => {
      const point = { label: formatChartDate(day.date), all: toPercent(day.rolling) };
      for (const habit of stats.habits) point[`h${habit.id}`] = toPercent(habit.series[offset + index]?.rolling);
      return point;
    });
  }, [stats, days]);

  return (
    <div className="flex h-full flex-col gap-2" data-testid="habits-chart">
      <p className="text-xs text-gray-500">Частка успішних днів за останні 7 днів, по кожній звичці й разом</p>
      <div className="min-h-[8rem] flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="label" minTickGap={28} tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <YAxis domain={[0, 100]} ticks={[0, 50, 100]} unit="%" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <Tooltip formatter={(value, name) => [value === null ? '—' : `${Math.round(value)}%`, name]} />
            {stats.habits.map((habit) => (
              <Line
                key={habit.id}
                type="monotone"
                dataKey={`h${habit.id}`}
                name={habit.name}
                stroke={colours[habit.id]}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
            <Line
              type="monotone"
              dataKey="all"
              name="Усі звички"
              stroke="#78716c"
              strokeDasharray="5 4"
              strokeWidth={2.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-700" data-testid="habits-chart-legend">
        {stats.habits.map((habit) => (
          <li key={habit.id} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colours[habit.id] }} />
            {habit.name} · {formatPercent(habit.rates['7'].success_rate)}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 border-t-2 border-dashed" style={{ borderColor: '#78716c' }} />
          Усі звички · {formatPercent(stats.summary.rates['7'].success_rate)}
        </li>
      </ul>
    </div>
  );
}

/** Every day coloured by how many of the habits judged that day were a success. */
export function HabitsHeatmapWidget({ stats, isLoading }) {
  return (
    <Gate stats={stats} isLoading={isLoading}>
      <HabitsHeatmap stats={stats} />
    </Gate>
  );
}

function HabitsHeatmap({ stats }) {
  const columns = useMemo(() => weekColumns(stats.daily), [stats.daily]);
  const cellView = (day) => {
    const head = formatDay(day.date);
    if (!day.judged) {
      return { className: 'bg-stone-100', title: `${head}: немає оцінених звичок` };
    }
    const shade = SHADES.find((item) => item.test(day.success_rate));
    const parts = [`успіх ${day.counts.success} з ${day.judged}`];
    if (day.counts.minimum) parts.push(`мінімум ${day.counts.minimum}`);
    if (day.counts.fail) parts.push(`порушень ${day.counts.fail}`);
    if (day.warnings) parts.push(`з попередженням ${day.warnings}`);
    return { style: { backgroundColor: shade.colour }, title: `${head}: ${parts.join(', ')}` };
  };

  return (
    <div className="flex h-full flex-col gap-3" data-testid="habits-heatmap">
      <p className="text-xs text-gray-500">
        Усі звички разом · {pluralCount(Math.round(stats.daily.length / 7), ['тиждень', 'тижні', 'тижнів'])}
      </p>
      <HeatmapGrid columns={columns} cellView={cellView} maxCell={20} testId="habits-heatmap-grid" />
      <ul className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-500">
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-stone-100" /> немає даних
        </li>
        {[...SHADES].reverse().map((item) => (
          <li key={item.colour} className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-[3px]" style={{ backgroundColor: item.colour }} /> {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
