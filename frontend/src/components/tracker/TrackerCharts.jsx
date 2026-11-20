import { CheckCircle2, Pencil, Trash2, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import DayStateLegend from '../cultivation/DayStateLegend';
import { DAY_STATUS_LABELS, dayStateCell, formatDay, formatNight, hasDayStates } from '../cultivation/helpers';
import HeatmapGrid from '../ui/HeatmapGrid';
import HabitDaysChart from './HabitDaysChart';
import { formatDate, formatTime, parseApiDate } from '../../utils/date';
import { formatNumber } from '../../utils/number';
import { WEEKDAY_SHORT } from '../../utils/labels';

const cardClass = 'w-full min-w-0 rounded-3xl border border-gray-100 bg-white p-5 shadow-sm md:p-6';
const chartAxisTick = { fontSize: 11, fill: '#9ca3af' };
const RECENT_LOGS = 10;

const pad = (value) => String(value).padStart(2, '0');
/** The viewer's calendar day of an API timestamp, as `YYYY-MM-DD`. */
const localDay = (value) => {
  const date = parseApiDate(value);
  return date ? `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` : '';
};
/** When a sleep began: the wake time less the hours slept, to the nearest minute. */
const bedtimeOf = (log) => {
  const wake = parseApiDate(log.timestamp);
  if (!wake) return null;
  return new Date(Math.round((wake.getTime() - log.amount * 3600000) / 60000) * 60000);
};

const HEATMAP_SHADES = ['bg-stone-100', 'bg-emerald-100', 'bg-emerald-200', 'bg-emerald-300', 'bg-emerald-500'];

const shadeFor = (intensity) => {
  if (intensity <= 0) return HEATMAP_SHADES[0];
  if (intensity < 0.25) return HEATMAP_SHADES[1];
  if (intensity < 0.5) return HEATMAP_SHADES[2];
  if (intensity < 0.75) return HEATMAP_SHADES[3];
  return HEATMAP_SHADES[4];
};

/** What a day marked by hand on the habit's page says, worded like a log's «Виконано». */
function MarkLabel({ status }) {
  if (status === 'fail') {
    return (
      <span className="inline-flex items-center gap-1.5 text-rose-600">
        <XCircle size={14} className="shrink-0" /> Не виконано
      </span>
    );
  }
  if (status === 'success') {
    return (
      <span className="inline-flex items-center gap-1.5">
        <CheckCircle2 size={14} className="shrink-0 text-emerald-600" /> Виконано
      </span>
    );
  }
  return <span>{DAY_STATUS_LABELS[status] || status}</span>;
}

function TrackerCharts({
  selectedTracker,
  historicalChartData,
  buildHeatmap,
  weekdayBreakdown,
  habitLogs,
  habitKind,
  habitMarks,
  habitLevel,
  habitTolerance,
  deleteLog,
  updateLog
}) {
  const [editingLogId, setEditingLogId] = useState(null);
  const [draftAmount, setDraftAmount] = useState('');

  const isQuit = selectedTracker.type === 'quit';
  const isBoolean = selectedTracker.type === 'boolean';
  // A sleep log is stamped at the wake time with the hours slept, and its day is the night before it.
  const isSleep = habitKind === 'sleep';
  const showsLogList = selectedTracker.type === 'build' || selectedTracker.type === 'boolean';

  const weekdayData = useMemo(
    () =>
      (weekdayBreakdown || []).map((entry) => ({
        ...entry,
        short: WEEKDAY_SHORT[entry.weekday] ?? entry.label.slice(0, 3)
      })),
    [weekdayBreakdown]
  );

  const hasWeekdayData = weekdayData.some((entry) => entry.entries > 0);

  // Logs and the days marked by hand, newest first. A mark has a day but no
  // time, so it is placed at the end of its day.
  const recentRows = useMemo(() => {
    const logs = habitLogs.map((log) => ({ log, time: parseApiDate(log.timestamp)?.getTime() ?? 0 }));
    const marks = (habitMarks || []).map((mark) => {
      const [year, month, day] = mark.date.split('-').map(Number);
      return { mark, time: new Date(year, month - 1, day, 23, 59, 59).getTime() };
    });
    return [...logs, ...marks].sort((a, b) => b.time - a.time).slice(0, RECENT_LOGS);
  }, [habitLogs, habitMarks]);
  const habitStates = hasDayStates(buildHeatmap);
  // A habit judged by an amount compares its days with the goal instead of totalling weekdays.
  const showsHabitDays = habitStates && (habitKind === 'build' || habitKind === 'sleep');

  const startEditing = (log) => {
    setEditingLogId(log.id);
    setDraftAmount(String(log.amount));
  };

  const saveEdit = async (logId) => {
    const amount = parseFloat(draftAmount);
    if (Number.isFinite(amount)) {
      await updateLog(logId, { amount });
    }
    setEditingLogId(null);
  };

  return (
    <div className="mb-8 grid gap-6 xl:grid-cols-2" data-testid="tracker-charts">
      <div className={cardClass}>
        <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
          <h2 className="text-sm font-semibold text-stone-700">Історія прогресу</h2>
          <p className="text-xs text-gray-400">Останні 120 днів</p>
        </div>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {isQuit ? (
              <LineChart data={historicalChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" minTickGap={35} tick={chartAxisTick} />
                <YAxis tick={chartAxisTick} allowDecimals={false} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#111827"
                  strokeWidth={2.5}
                  dot={false}
                  name="Днів серії"
                />
              </LineChart>
            ) : (
              <AreaChart data={historicalChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="progressArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#111827" stopOpacity={0.32} />
                    <stop offset="95%" stopColor="#111827" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" minTickGap={35} tick={chartAxisTick} />
                <YAxis tick={chartAxisTick} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#111827"
                  fill="url(#progressArea)"
                  strokeWidth={2.2}
                  name="Щоденна кількість"
                />
                <Line
                  type="monotone"
                  dataKey="cumulative"
                  stroke="#6b7280"
                  strokeWidth={1.4}
                  dot={false}
                  name="Накопичено"
                />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* The heatmap now covers quit trackers too, where a red cell marks a
          relapse — the clearest view of a pattern the streak number hides.
          A cultivated habit's map shows how each day was judged instead. */}
      {buildHeatmap && (
        <div className={cardClass}>
          <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <h2 className="text-sm font-semibold text-stone-700">
              {habitStates ? 'Теплова карта успіхів і порушень' : 'Теплова карта регулярності'}
            </h2>
            <p className="text-xs text-gray-400">Останні 24 тижні</p>
          </div>

          <HeatmapGrid
            columns={buildHeatmap.columns}
            testId="tracker-heatmap"
            cellView={(cell) => {
              if (habitStates) {
                const amount =
                  selectedTracker.type === 'build' && cell.amount > 0
                    ? `${formatNumber(cell.amount)} ${selectedTracker.unit}`
                    : '';
                return dayStateCell(cell, amount, habitKind);
              }
              const intensity = buildHeatmap.maxAmount > 0 ? cell.amount / buildHeatmap.maxAmount : 0;
              return {
                className: `border border-white/60 ${cell.isRelapse ? 'bg-rose-400' : shadeFor(intensity)}`,
                title: cell.isRelapse
                  ? `${cell.date}: записано зрив`
                  : isQuit
                    ? `${cell.date}: ${cell.amount > 0 ? 'день без зриву' : 'не відстежувалось'}`
                    : `${cell.date}: ${formatNumber(cell.amount)} ${selectedTracker.unit}`
              };
            }}
          />

          {habitStates ? (
            <DayStateLegend columns={buildHeatmap.columns} className="mt-4" />
          ) : (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
              <span>Менше</span>
              {HEATMAP_SHADES.map((shade) => (
                <span key={shade} className={`h-3.5 w-3.5 rounded-[3px] border border-white/60 ${shade}`} />
              ))}
              <span>Більше</span>
              {isQuit && (
                <>
                  <span className="ml-3 h-3.5 w-3.5 rounded-[3px] border border-white/60 bg-rose-400" />
                  <span>Зрив</span>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {showsHabitDays && (
        <HabitDaysChart
          columns={buildHeatmap.columns}
          kind={habitKind}
          level={habitLevel}
          tolerance={habitTolerance}
          unit={selectedTracker.unit}
          className={cardClass}
        />
      )}

      {!isQuit && !showsHabitDays && hasWeekdayData && (
        <div className={cardClass}>
          <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <h2 className="text-sm font-semibold text-stone-700">У які дні ви найактивніші</h2>
            <p className="text-xs text-gray-400">Підсумки за весь час за днями тижня</p>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weekdayData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                <XAxis dataKey="short" tick={chartAxisTick} />
                <YAxis tick={chartAxisTick} />
                <Tooltip
                  formatter={(value) => [`${value} ${selectedTracker.unit}`, 'Разом']}
                  labelFormatter={(label) => weekdayData.find((entry) => entry.short === label)?.label || label}
                />
                <Bar dataKey="total" fill="#111827" radius={[6, 6, 0, 0]} name="Разом" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {showsLogList && recentRows.length > 0 && (
        <div className={`${cardClass} xl:col-span-2`} data-testid="recent-logs">
          <div className="mb-3 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <h2 className="text-sm font-semibold text-stone-700">Останні записи</h2>
            <p className="text-xs text-gray-400">До {RECENT_LOGS} найновіших</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-gray-400">
                <tr>
                  {isSleep ? (
                    <>
                      <th className="py-1.5 pr-4 font-medium">Ніч</th>
                      <th className="py-1.5 pr-4 font-medium">Заснув</th>
                      <th className="py-1.5 pr-4 font-medium">Підйом</th>
                      <th className="py-1.5 pr-4 font-medium">Сон</th>
                    </>
                  ) : (
                    <>
                      <th className="py-1.5 pr-4 font-medium">Дата</th>
                      <th className="py-1.5 pr-4 font-medium">Час</th>
                      <th className="py-1.5 pr-4 font-medium">{isBoolean ? 'Запис' : 'Кількість'}</th>
                    </>
                  )}
                  <th className="py-1.5 pr-4 font-medium">Нотатка</th>
                  <th className="py-1.5 font-medium">
                    <span className="sr-only">Дії</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map(({ log, mark }) =>
                  mark ? (
                    <tr
                      key={`mark-${mark.date}`}
                      className="border-t border-gray-100 align-middle"
                      data-testid="recent-log"
                      data-mark={mark.status}
                      title="Позначено вручну"
                    >
                      <td className="whitespace-nowrap py-2 pr-4 text-stone-800">
                        {isSleep
                          ? formatNight(mark.date, 'short')
                          : formatDay(mark.date, { weekday: 'short', day: 'numeric', month: 'short' })}
                      </td>
                      {isSleep && <td className="py-2 pr-4 text-gray-400">—</td>}
                      <td className="py-2 pr-4 text-gray-400">—</td>
                      <td className="whitespace-nowrap py-2 pr-4 font-medium text-stone-900">
                        <MarkLabel status={mark.status} />
                      </td>
                      <td className="py-2 pr-4 text-gray-500">{mark.reason || '—'}</td>
                      <td className="py-2" />
                    </tr>
                  ) : (
                    <tr key={log.id} className="border-t border-gray-100 align-middle" data-testid="recent-log">
                      {isSleep ? (
                        <>
                          <td className="whitespace-nowrap py-2 pr-4 text-stone-800">
                            {formatNight(localDay(log.timestamp), 'short')}
                          </td>
                          <td className="whitespace-nowrap py-2 pr-4 text-stone-800">{formatTime(bedtimeOf(log))}</td>
                          <td className="whitespace-nowrap py-2 pr-4 text-stone-800">{formatTime(log.timestamp)}</td>
                        </>
                      ) : (
                        <>
                          <td className="whitespace-nowrap py-2 pr-4 text-stone-800">
                            {formatDate(log.timestamp, { weekday: 'short', day: 'numeric', month: 'short' })}
                          </td>
                          <td className="whitespace-nowrap py-2 pr-4 text-stone-800">{formatTime(log.timestamp)}</td>
                        </>
                      )}
                      <td className="whitespace-nowrap py-2 pr-4 font-medium text-stone-900">
                        {editingLogId === log.id ? (
                          <span className="flex items-center gap-2">
                            <input
                              type="number"
                              step="any"
                              value={draftAmount}
                              onChange={(event) => setDraftAmount(event.target.value)}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') saveEdit(log.id);
                                if (event.key === 'Escape') setEditingLogId(null);
                              }}
                              className="w-20 rounded-lg border border-gray-200 px-2 py-1 text-sm outline-none focus:border-stone-400"
                              aria-label="Кількість"
                              autoFocus
                            />
                            <button
                              type="button"
                              onClick={() => saveEdit(log.id)}
                              className="rounded-lg bg-stone-900 px-2 py-1 text-xs font-medium text-white"
                            >
                              Зберегти
                            </button>
                          </span>
                        ) : isBoolean ? (
                          <span className="inline-flex items-center gap-1.5">
                            <CheckCircle2 size={14} className="shrink-0 text-emerald-600" /> Виконано
                          </span>
                        ) : (
                          `${formatNumber(log.amount)} ${selectedTracker.unit}`
                        )}
                      </td>
                      <td className="py-2 pr-4 text-gray-500">{log.note || '—'}</td>
                      <td className="py-2">
                        <span className="flex justify-end gap-2">
                          {!isBoolean && (
                            <button
                              type="button"
                              onClick={() => startEditing(log)}
                              className="text-gray-400 hover:text-stone-700"
                              aria-label="Редагувати цей запис"
                            >
                              <Pencil size={14} />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => deleteLog(log.id)}
                            className="text-gray-400 hover:text-rose-500"
                            aria-label="Видалити цей запис"
                          >
                            <Trash2 size={14} />
                          </button>
                        </span>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default TrackerCharts;
