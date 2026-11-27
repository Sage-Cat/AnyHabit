import { formatDay, useCultivationOverview } from '../../cultivation/helpers';
import { WidgetEmptyState, WidgetLoading } from './shared';

/**
 * Habits still waiting for a record: the status only, nothing to tap. The
 * server decides what is awaited — paused, quit and off-schedule habits never
 * are, and an evening habit before 06:00 still waits for the evening before.
 */
export function PendingHabitsWidget() {
  const { overview, isLoading, error } = useCultivationOverview();

  if (isLoading && !overview) return <WidgetLoading />;
  if (error || !overview) return <WidgetEmptyState title="Звички недоступні" hint="Спробуйте оновити сторінку." />;

  const pending = [...overview.active, ...overview.integrated].filter((habit) => habit.today?.pending);
  if (pending.length === 0) {
    return (
      <div data-testid="pending-habits-empty" className="h-full">
        <WidgetEmptyState title="Усе на сьогодні записано" />
      </div>
    );
  }

  return (
    // Borders, not divide-*: the dark theme repaints border-gray-100 only.
    <ul data-testid="pending-habits">
      {pending.map((habit) => {
        const { requirement, pending_for: awaited, date } = habit.today;
        return (
          <li
            key={habit.id}
            className="flex items-start justify-between gap-3 border-b border-gray-100 py-2 last:border-b-0"
            data-testid="pending-habit"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-stone-800">{habit.name}</p>
              {requirement && requirement !== 'виконати' && <p className="text-xs text-gray-500">{requirement}</p>}
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-gray-500">
              <span className="h-2.5 w-2.5 rounded-full bg-stone-300" aria-hidden="true" />
              {awaited && awaited !== date ? `без запису за ${formatDay(awaited)}` : 'без запису'}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
