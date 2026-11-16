/**
 * Calendar heatmap: one column per week, one row per weekday. Cells grow with
 * the card up to `maxCell` pixels, so a wide card is filled instead of leaving
 * a small grid in one corner, and a narrow one still fits without scrolling.
 *
 * `cellView(cell)` returns `{ className, style, title, state }` for one cell;
 * `state` lands in `data-state`, so a cell's meaning can be checked without its colour.
 */
function HeatmapGrid({ columns, cellView, maxCell = 22, testId }) {
  if (!columns?.length) return null;
  return (
    <div
      className="grid gap-[3px]"
      style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, ${maxCell}px))` }}
      data-testid={testId}
    >
      {columns.map((week, weekIndex) => (
        <div key={`week-${weekIndex}`} className="grid auto-rows-min gap-[3px]">
          {week.map((cell) => {
            if (cell.isFiller) return <div key={cell.date} className="aspect-square w-full" aria-hidden="true" />;
            const view = cellView(cell);
            return (
              <div
                key={cell.date}
                title={view.title}
                data-date={cell.date}
                data-state={view.state}
                className={`aspect-square w-full rounded-[3px] ${view.className || ''}`}
                style={view.style}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

export default HeatmapGrid;
