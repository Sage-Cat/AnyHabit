import { useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatChartDate } from '../../utils/labels';
import { DAY_MS, STAGE_META, toIso, toTime } from './stageMeta';

/** «Прорив»: how far the way to the next rank is, in percent. */
export function Breakthrough({ next }) {
  if (!next || next.breakthrough == null) return null;
  const percent = Math.max(0, Math.min(100, next.breakthrough));
  return (
    <div data-testid="breakthrough">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 text-sm text-gray-600">
          <span className="font-semibold text-stone-800">Прорив</span> до «{next.name}»
        </p>
        <p className="text-xl font-bold text-stone-900" data-testid="breakthrough-percent">
          {percent}%
        </p>
      </div>
      <div
        className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-stone-100"
        role="progressbar"
        aria-label={`Прорив до рангу «${next.name}»`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${percent}%`, background: 'linear-gradient(90deg, #8b5cf6, #10b981)' }}
        />
      </div>
    </div>
  );
}

/** How many habits are at each stage right now. */
export function StageCounts({ stages }) {
  if (!stages) return null;
  const total = STAGE_META.reduce((sum, stage) => sum + (stages[stage.key] || 0), 0);
  return (
    <div className="space-y-2" data-testid="stage-counts">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(5rem,1fr))] gap-2">
        {STAGE_META.map((stage) => (
          <div key={stage.key} className="rounded-xl bg-stone-50 px-2.5 py-2" data-testid={`stage-count-${stage.key}`}>
            <p className="flex items-center gap-1.5 text-[11px] text-gray-500">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: stage.colour }} />
              {stage.label}
            </p>
            <p className="text-xl font-semibold text-stone-900">{stages[stage.key] || 0}</p>
          </div>
        ))}
      </div>
      {total > 0 && (
        <div className="flex h-2 overflow-hidden rounded-full" role="img" aria-label="Звички за етапами">
          {STAGE_META.filter((stage) => stages[stage.key]).map((stage) => (
            <span
              key={stage.key}
              style={{ width: `${(stages[stage.key] / total) * 100}%`, backgroundColor: stage.colour }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** Habits per stage over time: a stacked step chart from the first habit to today. */
export function StageTimeline({ timeline, height = 140 }) {
  const { data, ticks } = useMemo(() => {
    const points = (timeline || []).map((point) => ({ ...point, time: toTime(point.date) }));
    if (!points.length) return { data: points, ticks: [] };
    const first = points[0].time;
    const last = points[points.length - 1].time;
    // One more day at the end, so a change made today shows as a step rather than a line.
    points.push({ ...points[points.length - 1], time: last + DAY_MS });
    const step = Math.max(1, Math.ceil((last - first) / DAY_MS / 4)) * DAY_MS;
    const marks = [];
    for (let time = first; time < last; time += step) marks.push(time);
    marks.push(last);
    return { data: points, ticks: marks };
  }, [timeline]);
  if (!data.length) return null;
  return (
    <div data-testid="stage-timeline">
      <p className="mb-1 text-xs text-gray-500">Звички за етапами в часі</p>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              ticks={ticks}
              tickFormatter={(time) => formatChartDate(toIso(time))}
              tick={{ fontSize: 10, fill: '#9ca3af' }}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <Tooltip labelFormatter={(time) => formatChartDate(toIso(time))} />
            {STAGE_META.map((stage) => (
              <Area
                key={stage.key}
                type="stepAfter"
                dataKey={stage.key}
                name={stage.label}
                stackId="stages"
                stroke={stage.colour}
                fill={stage.colour}
                fillOpacity={0.35}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
