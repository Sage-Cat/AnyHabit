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

/** The passport's thresholds, drawn across the chart; sleep is judged by hours. */
function thresholdLines(kind, level, tolerance, unit) {
  const lines = [];
  if (kind === 'sleep') {
    const hours = (value) => `${amountText(value)} год`;
    if (level?.min_sleep_h != null) lines.push({ y: level.min_sleep_h, label: `Ціль від ${hours(level.min_sleep_h)}` });
    if (level?.max_sleep_h != null) lines.push({ y: level.max_sleep_h, label: `Ціль до ${hours(level.max_sleep_h)}` });
    if (tolerance?.min_sleep_h != null)
      lines.push({ y: tolerance.min_sleep_h, label: `Допуск від ${hours(tolerance.min_sleep_h)}`, tolerance: true });
    if (tolerance?.max_sleep_h != null)
      lines.push({ y: tolerance.max_sleep_h, label: `Допуск до ${hours(tolerance.max_sleep_h)}`, tolerance: true });
  } else {
    if (level?.min_amount != null)
      lines.push({ y: level.min_amount, label: `Ціль ${amountText(level.min_amount)} ${unit}`.trim() });
    if (tolerance?.min_amount != null)
      lines.push({
        y: tolerance.min_amount,
        label: `Допуск ${amountText(tolerance.min_amount)} ${unit}`.trim(),
        tolerance: true
      });
  }
  // The highest label sits above its line, the rest below, so close lines do not overlap
  // (Recharts puts an inside-bottom label above a horizontal line).
  return lines
    .map((line) => ({ ...line, y: Number(line.y) }))
    .sort((a, b) => b.y - a.y)
    .map((line, index) => ({ ...line, position: index === 0 ? 'insideBottomRight' : 'insideTopRight' }));
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
  const lines = thresholdLines(kind, level, tolerance, unit);

  return (
    <div className={className} data-testid="habit-days-chart">
      <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <h2 className="text-sm font-semibold text-stone-700">Дні порівняно з ціллю</h2>
        <p className="text-xs text-gray-400">{kind === 'sleep' ? 'Останні 30 ночей' : 'Останні 30 днів'}</p>
      </div>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={days} margin={{ top: 16, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="tick" tick={AXIS_TICK} minTickGap={8} />
            <YAxis tick={AXIS_TICK} tickFormatter={amountText} />
            <Tooltip cursor={{ fill: '#f5f5f4' }} content={<DayTip kind={kind} unit={unit} />} />
            <Bar dataKey="amount" radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false}>
              {days.map((day) => (
                <Cell key={day.date} fill={dayFill(day)} />
              ))}
            </Bar>
            {lines.map((line) => {
              const color = line.tolerance ? TOLERANCE_COLOR : GOAL_COLOR;
              return (
                <ReferenceLine
                  key={line.label}
                  y={line.y}
                  stroke={color}
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                  ifOverflow="extendDomain"
                  label={{ value: line.label, position: line.position, fill: color, fontSize: 11 }}
                />
              );
            })}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <DayStateLegend columns={[days]} className="mt-4" />
    </div>
  );
}

export default HabitDaysChart;
