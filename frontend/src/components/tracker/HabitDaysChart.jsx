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
const HOUR = 60;
const AXIS_TICK = { fontSize: 11, fill: '#9ca3af' };
const GOAL_COLOR = '#059669';
const TOLERANCE_COLOR = '#d97706';
const UNKNOWN_OPACITY = 0.35;

const amountText = (value) => formatNumber(value, Number.isInteger(Number(value)) ? 0 : 1);
const minutesOf = (clock) => {
  const [hours, minutes] = String(clock).split(':').map(Number);
  return hours * HOUR + minutes;
};
const clockText = (minutes) =>
  `${String(Math.floor(minutes / HOUR) % 24).padStart(2, '0')}:${String(minutes % HOUR).padStart(2, '0')}`;

/**
 * What a day's bar measures: hours slept, the amount logged, the time a
 * "done by" habit was done, or, with nothing to measure, only the day's verdict.
 */
function scaleOf(kind, level, tolerance) {
  if (kind === 'sleep') return 'hours';
  if (kind === 'build') return 'amount';
  if (kind === 'boolean' && (level?.done_by || tolerance?.done_by)) return 'time';
  return 'state';
}

/** A day's axis label: the date, or for sleep the night before the wake date. */
function tickOf(kind, value) {
  const [year, month, day] = value.split('-').map(Number);
  if (kind === 'sleep') return `${new Date(year, month - 1, day - 1).getDate()}–${day}`;
  return `${day}.${String(month).padStart(2, '0')}`;
}

/** A passport level's bounds on the chart's scale. */
function boundsOf(scale, spec) {
  if (scale === 'time') return spec?.done_by ? [minutesOf(spec.done_by)] : [];
  const bounds = scale === 'hours' ? [spec?.min_sleep_h, spec?.max_sleep_h] : [spec?.min_amount];
  return scale === 'state' ? [] : bounds.filter((value) => value != null).map(Number);
}

/** Bounds as words: "7–10 год", "від 7 год", "до 10 год", "≥ 5 000 кроків", "до 21:00". */
function boundsText(scale, spec, unit) {
  if (scale === 'time') return spec?.done_by ? `до ${spec.done_by}` : '';
  if (scale === 'amount') return spec?.min_amount != null ? `≥ ${amountText(spec.min_amount)} ${unit}`.trim() : '';
  if (scale !== 'hours') return '';
  const [low, high] = [spec?.min_sleep_h, spec?.max_sleep_h];
  if (low != null && high != null) return `${amountText(low)}–${amountText(high)} год`;
  if (low != null) return `від ${amountText(low)} год`;
  if (high != null) return `до ${amountText(high)} год`;
  return '';
}

/**
 * The passport's thresholds: one line per distinct value (a tolerance bound equal to
 * the goal's is the same line) and a legend naming them, so no text sits on the bars.
 */
function thresholds(scale, level, tolerance, unit) {
  const goal = boundsOf(scale, level);
  const lines = [
    ...goal.map((y) => ({ y, color: GOAL_COLOR })),
    ...boundsOf(scale, tolerance)
      .filter((y) => !goal.includes(y))
      .map((y) => ({ y, color: TOLERANCE_COLOR }))
  ];
  const goalText = boundsText(scale, level, unit);
  const toleranceText = boundsText(scale, tolerance, unit);
  const legend = [];
  if (goalText && goalText === toleranceText) legend.push({ label: `Ціль і допуск: ${goalText}`, color: GOAL_COLOR });
  else {
    if (goalText) legend.push({ label: `Ціль: ${goalText}`, color: GOAL_COLOR });
    if (toleranceText) legend.push({ label: `Допуск: ${toleranceText}`, color: TOLERANCE_COLOR });
  }
  return { lines, legend };
}

/**
 * Whole hours around the done times and the lines. A judged day without a
 * time (a day marked by hand) is drawn pale up to the top: its verdict is
 * known, its time is not.
 */
function timeAxis(days, lines) {
  const known = [...days.map((day) => day.value).filter((value) => value != null), ...lines.map((line) => line.y)];
  if (!known.length) return null;
  const low = Math.max(0, Math.floor((Math.min(...known) - HOUR) / HOUR) * HOUR);
  const high = Math.ceil((Math.max(...known) + HOUR / 2) / HOUR) * HOUR;
  const ticks = [];
  for (let tick = low; tick <= high; tick += HOUR) ticks.push(tick);
  return { domain: [low, high], ticks };
}

function DayTip({ active, payload, kind, scale, unit }) {
  if (!active || !payload?.length) return null;
  const day = payload[0].payload;
  let measure = null;
  if (scale === 'time') measure = day.unknown ? 'час не записано' : `виконано о ${day.firstAt}`;
  else if (scale !== 'state') measure = `${amountText(day.value)} ${unit}`;
  return (
    <div className="rounded-xl border border-gray-100 bg-white px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-stone-800">{formatHabitDay(kind, day.date)}</p>
      {measure && <p className="text-stone-600">{measure}</p>}
      <p className="text-stone-500">{dayLabel(day)}</p>
    </div>
  );
}

/**
 * A cultivated habit's recent days as bars, each coloured by how the day was
 * judged, with the passport's goal and tolerance drawn across them.
 */
function HabitDaysChart({ columns, kind, level, tolerance, unit = '', className = '' }) {
  const scale = scaleOf(kind, level, tolerance);
  const valueOf = (cell) => {
    if (scale === 'time') return cell.firstAt ? minutesOf(cell.firstAt) : null;
    if (scale === 'state') return cell.status === 'no_data' ? null : 1;
    return cell.amount;
  };
  let days = (columns || [])
    .flat()
    .filter((cell) => !cell.isFiller && cell.status)
    .slice(-DAYS)
    .map((cell) => ({ ...cell, tick: tickOf(kind, cell.date), value: valueOf(cell) }));
  if (!days.length) return null;
  const { lines, legend } = thresholds(scale, level, tolerance, unit);
  const axis = scale === 'time' ? timeAxis(days, lines) : null;
  if (axis) {
    days = days.map((day) =>
      day.value == null && day.status !== 'no_data' ? { ...day, value: axis.domain[1], unknown: true } : day
    );
  }
  const hasUnknown = days.some((day) => day.unknown);

  let yAxis = <YAxis tick={AXIS_TICK} tickFormatter={amountText} />;
  if (axis) yAxis = <YAxis tick={AXIS_TICK} domain={axis.domain} ticks={axis.ticks} tickFormatter={clockText} />;
  else if (scale === 'state') yAxis = <YAxis hide domain={[0, 1]} />;

  return (
    <div className={className} data-testid="habit-days-chart">
      <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <h2 className="text-sm font-semibold text-stone-700">Дні порівняно з ціллю</h2>
        <p className="text-xs text-gray-400">{kind === 'sleep' ? 'Останні 30 ночей' : 'Останні 30 днів'}</p>
      </div>
      {(legend.length > 0 || hasUnknown) && (
        <ul className="-mt-2 mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px]" data-testid="threshold-legend">
          {legend.map((item) => (
            <li key={item.label} className="flex items-center gap-1.5" style={{ color: item.color }}>
              <span className="w-4 border-t-2 border-dashed" style={{ borderColor: item.color }} />
              {item.label}
            </li>
          ))}
          {hasUnknown && (
            <li className="flex items-center gap-1.5 text-gray-400" data-testid="unknown-time-note">
              <span className="h-3 w-3 rounded-[3px] bg-gray-400" style={{ opacity: UNKNOWN_OPACITY }} />
              Блідий стовпець — час не записано
            </li>
          )}
        </ul>
      )}
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={days} margin={{ top: 8, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
            <XAxis dataKey="tick" tick={AXIS_TICK} minTickGap={8} />
            {yAxis}
            <Tooltip cursor={{ fill: '#f5f5f4' }} content={<DayTip kind={kind} scale={scale} unit={unit} />} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={48} isAnimationActive={false}>
              {days.map((day) => (
                <Cell key={day.date} fill={dayFill(day)} fillOpacity={day.unknown ? UNKNOWN_OPACITY : 1} />
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
