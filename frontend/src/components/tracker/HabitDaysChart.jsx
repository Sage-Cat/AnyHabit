import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import DayStateLegend from '../cultivation/DayStateLegend';
import { dayFill, dayLabel, formatHabitDay } from '../cultivation/helpers';
import { formatNumber } from '../../utils/number';

const DAYS = 30;
const AXIS_TICK = { fontSize: 11, fill: '#9ca3af' };
const GOAL_COLOR = '#059669';
const TOLERANCE_COLOR = '#d97706';

const amountText = (value) => formatNumber(value, Number.isInteger(Number(value)) ? 0 : 1);

/** A day's axis label: the date, or for sleep the night before the wake date. */
function tickOf(kind, value) {
  const [year, month, day] = value.split('-').map(Number);
  if (kind === 'sleep') return `${new Date(year, month - 1, day - 1).getDate()}–${day}`;
  return `${day}.${String(month).padStart(2, '0')}`;
}

/** A passport level's bounds on the chart's scale: sleep is judged by hours. */
function boundsOf(kind, spec) {
  const [low, high] = kind === 'sleep' ? [spec?.min_sleep_h, spec?.max_sleep_h] : [spec?.min_amount, null];
  return [low, high].filter((value) => value != null).map(Number);
}

/** Bounds as words: "7–10 год", "від 7 год", "до 10 год", "≥ 5 000 кроків". */
function boundsText(kind, spec, unit) {
  const suffix = kind === 'sleep' ? 'год' : unit;
  const [low, high] = kind === 'sleep' ? [spec?.min_sleep_h, spec?.max_sleep_h] : [spec?.min_amount, null];
  let text = '';
  if (low != null && high != null) text = `${amountText(low)}–${amountText(high)}`;
  else if (low != null) text = kind === 'sleep' ? `від ${amountText(low)}` : `≥ ${amountText(low)}`;
  else if (high != null) text = `до ${amountText(high)}`;
  return text && `${text} ${suffix}`.trim();
}

/**
 * The passport's thresholds: one line per distinct value (a tolerance bound equal to
 * the goal's is the same line) and a legend naming them, so no text sits on the bars.
 */
function thresholds(kind, level, tolerance, unit) {
  const goal = boundsOf(kind, level);
  const lines = [
    ...goal.map((y) => ({ y, color: GOAL_COLOR })),
    ...boundsOf(kind, tolerance)
      .filter((y) => !goal.includes(y))
      .map((y) => ({ y, color: TOLERANCE_COLOR }))
  ];
  const goalText = boundsText(kind, level, unit);
  const toleranceText = boundsText(kind, tolerance, unit);
  const legend = [];
  if (goalText && goalText === toleranceText) legend.push({ label: `Ціль і допуск: ${goalText}`, color: GOAL_COLOR });
  else {
    if (goalText) legend.push({ label: `Ціль: ${goalText}`, color: GOAL_COLOR });
    if (toleranceText) legend.push({ label: `Допуск: ${toleranceText}`, color: TOLERANCE_COLOR });
  }
  return { lines, legend };
}

function DayTip({ active, payload, kind, unit }) {
  if (!active || !payload?.length) return null;
  const day = payload[0].payload;
  return (
    <div className="rounded-xl border border-gray-100 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-stone-800">{formatHabitDay(kind, day.date)}</p>
      <p className="text-stone-600">
        {amountText(day.amount)} {unit}
      </p>
      <p className="text-stone-500">{dayLabel(day)}</p>
    </div>
  );
}

/**
 * A cultivated habit's recent days as bars, each coloured by how the day was
 * judged, with the passport's goal and tolerance drawn across them.
 */
function HabitDaysChart({ columns, kind, level, tolerance, unit = '', className = '' }) {
  const days = (columns || [])
    .flat()
    .filter((cell) => !cell.isFiller && cell.status)
    .slice(-DAYS)
    .map((cell) => ({ ...cell, tick: tickOf(kind, cell.date) }));
  if (!days.length) return null;
  const { lines, legend } = thresholds(kind, level, tolerance, unit);

  return (
    <div className={className} data-testid="habit-days-chart">
      <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <h2 className="text-sm font-semibold text-stone-700">Дні порівняно з ціллю</h2>
        <p className="text-xs text-gray-400">{kind === 'sleep' ? 'Останні 30 ночей' : 'Останні 30 днів'}</p>
      </div>
      {legend.length > 0 && (
        <ul className="-mt-2 mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px]" data-testid="threshold-legend">
          {legend.map((item) => (
            <li key={item.label} className="flex items-center gap-1.5" style={{ color: item.color }}>
              <span className="w-4 border-t-2 border-dashed" style={{ borderColor: item.color }} />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={days} margin={{ top: 8, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="tick" tick={AXIS_TICK} minTickGap={8} />
            <YAxis tick={AXIS_TICK} tickFormatter={amountText} />
            <Tooltip cursor={{ fill: '#f5f5f4' }} content={<DayTip kind={kind} unit={unit} />} />
            <Bar dataKey="amount" radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false}>
              {days.map((day) => (
                <Cell key={day.date} fill={dayFill(day)} />
              ))}
            </Bar>
            {lines.map((line) => (
              <ReferenceLine
                key={line.y}
                y={line.y}
                stroke={line.color}
                strokeDasharray="6 4"
                strokeWidth={1.5}
                ifOverflow="extendDomain"
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <DayStateLegend columns={[days]} className="mt-4" />
    </div>
  );
}

export default HabitDaysChart;
