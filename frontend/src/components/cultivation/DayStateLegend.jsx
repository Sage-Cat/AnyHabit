import { DAY_STATUS_LABELS, DAY_STATUS_STYLES, WARNING_LABEL, WARNING_STYLE } from './helpers';

const ORDER = ['success', 'warning', 'minimum', 'fail', 'exception', 'no_data', 'unrated', 'invalid'];

/** Legend of the day states on a habit's heatmap; success and failure always, so the scale reads. */
function DayStateLegend({ columns, className = '' }) {
  const seen = new Set(['success', 'fail']);
  for (const week of columns || []) {
    for (const cell of week) {
      if (cell.status) seen.add(cell.status === 'success' && cell.warning ? 'warning' : cell.status);
    }
  }
  return (
    <ul
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-500 ${className}`}
      data-testid="day-state-legend"
    >
      {ORDER.filter((key) => seen.has(key)).map((key) => (
        <li key={key} className="flex items-center gap-1.5">
          <span className={`h-3 w-3 rounded-[3px] ${key === 'warning' ? WARNING_STYLE : DAY_STATUS_STYLES[key]}`} />
          {key === 'warning' ? WARNING_LABEL : DAY_STATUS_LABELS[key]}
        </li>
      ))}
    </ul>
  );
}

export default DayStateLegend;
