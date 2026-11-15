/** Group consecutive days (oldest first) into Monday-first week columns, padding the first week. */
export function weekColumns(days) {
  if (!days?.length) return [];
  const [year, month, day] = days[0].date.split('-').map(Number);
  const offset = (new Date(year, month - 1, day).getDay() + 6) % 7;
  const cells = [...Array.from({ length: offset }, (_, index) => ({ date: `pad-${index}`, isFiller: true })), ...days];
  const columns = [];
  for (let index = 0; index < cells.length; index += 7) columns.push(cells.slice(index, index + 7));
  return columns;
}
