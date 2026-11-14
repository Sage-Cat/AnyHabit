import {
  Archive,
  ArchiveRestore,
  Calendar,
  CheckCircle2,
  Clock,
  Menu,
  Pause,
  Pencil,
  Play,
  PlusCircle,
  RotateCcw,
  Target,
  Trash2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { TRACKER_COLOR_HEX, TRACKER_TYPE_LABELS } from '../../constants/tracker';
import { formatDateTime } from '../../utils/date';
import { plural } from '../../utils/plural';
import { categoryLabel, formatScheduleLabel, normalizeCategory } from '../../utils/tracker';


function TrackerHeader({
  selectedTracker,
  canManageTracker,
  dailyProgress,
  effectiveStartDate,
  setIsSidebarOpen,
  setSelectedCategory,
  setIsLogModalOpen,
  setLogFormData,
  onQuickBooleanLog,
  handleResetTracker,
  toggleTrackerStatus,
  archiveTracker,
  unarchiveTracker,
  openTrackerModal,
  deleteTracker
}) {
  const navigate = useNavigate();
  const isArchived = Boolean(selectedTracker.archived_at);
  const accent = TRACKER_COLOR_HEX[selectedTracker.color];

  const ownerOnlyClass = canManageTracker
    ? 'bg-white border border-gray-200 text-stone-700 hover:bg-gray-50'
    : 'bg-stone-100 border border-stone-200 text-stone-400 cursor-not-allowed';

  const category = normalizeCategory(selectedTracker.category);
  const hasRestarted =
    effectiveStartDate && new Date(effectiveStartDate).getTime() !== new Date(selectedTracker.start_date).getTime();

  return (
    <header className="flex flex-col px-4 pb-6 pt-6 md:px-10 md:pt-10">
      <div className="flex w-full flex-col items-start justify-between gap-4 xl:flex-row">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="mr-1 text-stone-500 hover:text-stone-900 md:hidden"
              aria-label="Відкрити навігацію"
            >
              <Menu size={24} />
            </button>

            {accent && (
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: accent }}
                aria-hidden="true"
              />
            )}

            <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{selectedTracker.name}</h1>

            <button
              type="button"
              onClick={() => {
                setSelectedCategory(category);
                navigate(`/category/${encodeURIComponent(category)}`);
              }}
              className="rounded-md bg-stone-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-stone-600 transition-colors hover:bg-stone-200"
            >
              {categoryLabel(category)}
            </button>

            <span className="rounded-md bg-stone-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-stone-800">
              {TRACKER_TYPE_LABELS[selectedTracker.type] || selectedTracker.type}
            </span>

            {selectedTracker.group_id && (
              <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                Спільна{selectedTracker.participant_count ? ` · ${selectedTracker.participant_count} ${plural(selectedTracker.participant_count, ['учасник', 'учасники', 'учасників'])}` : ''}
              </span>
            )}

            {isArchived && (
              <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-700">
                В архіві
              </span>
            )}

            {!selectedTracker.is_active && !isArchived && (
              <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                На паузі
              </span>
            )}
          </div>

          {selectedTracker.description && (
            <p className="mt-2 max-w-2xl whitespace-pre-wrap text-sm leading-6 text-stone-600">
              {selectedTracker.description}
            </p>
          )}

          <div className="mt-3 flex flex-col gap-1">
            <p className="flex items-center gap-2 text-sm text-gray-500">
              <Target size={14} className="shrink-0" />
              {selectedTracker.type === 'boolean'
                ? formatScheduleLabel(selectedTracker)
                : selectedTracker.type === 'quit'
                  ? `Уникати: ${formatScheduleLabel(selectedTracker)}`
                  : `Ціль: ${formatScheduleLabel(selectedTracker)}`}
            </p>

            <p className="flex items-center gap-2 text-sm text-gray-500">
              <Calendar size={14} className="shrink-0" />
              Початок: {formatDateTime(selectedTracker.start_date)}
            </p>

            {/* After a relapse the two dates diverge; showing both makes the
                reset legible instead of looking like lost history. */}
            {hasRestarted && (
              <p className="flex items-center gap-2 text-sm text-gray-500">
                <Clock size={14} className="shrink-0" />
                Поточна серія з {formatDateTime(effectiveStartDate)}
              </p>
            )}
          </div>
        </div>

        <div className="flex w-full flex-wrap gap-2 xl:w-auto">
          {!isArchived && selectedTracker.type === 'build' && (
            <button
              onClick={() => {
                setLogFormData({ amount: 1, note: '', timestamp: new Date().toISOString() });
                setIsLogModalOpen(true);
              }}
              className="flex items-center gap-2 rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-800"
            >
              <PlusCircle size={16} /> Додати запис
            </button>
          )}

          {!isArchived && selectedTracker.type === 'boolean' && dailyProgress.total < dailyProgress.target && (
            <button
              onClick={onQuickBooleanLog}
              className="flex items-center gap-2 rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-800"
            >
              <CheckCircle2 size={16} /> Позначити виконаним
            </button>
          )}

          {!isArchived && selectedTracker.type === 'quit' && (
            <button
              onClick={() => handleResetTracker(selectedTracker.id)}
              className="flex items-center gap-2 rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-800"
            >
              <RotateCcw size={16} /> Записати зрив
            </button>
          )}

          {!isArchived && (
            <button
              onClick={() => canManageTracker && toggleTrackerStatus(selectedTracker)}
              disabled={!canManageTracker}
              title={!canManageTracker ? 'Лише власник може це зробити' : undefined}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${ownerOnlyClass}`}
            >
              {selectedTracker.is_active ? (
                <>
                  <Pause size={16} /> Пауза
                </>
              ) : (
                <>
                  <Play size={16} /> Відновити
                </>
              )}
            </button>
          )}

          <button
            onClick={() =>
              canManageTracker &&
              (isArchived ? unarchiveTracker(selectedTracker.id) : archiveTracker(selectedTracker.id))
            }
            disabled={!canManageTracker}
            title={
              !canManageTracker
                ? 'Лише власник може це зробити'
                : isArchived
                  ? 'Повернути цю звичку'
                  : 'Сховати звичку, зберігши всю історію'
            }
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${ownerOnlyClass}`}
          >
            {isArchived ? (
              <>
                <ArchiveRestore size={16} /> Повернути
              </>
            ) : (
              <>
                <Archive size={16} /> Архівувати
              </>
            )}
          </button>

          <button
            onClick={() => canManageTracker && openTrackerModal(selectedTracker)}
            disabled={!canManageTracker}
            title={!canManageTracker ? 'Лише власник може це зробити' : undefined}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${ownerOnlyClass}`}
          >
            <Pencil size={16} /> Редагувати
          </button>

          <button
            onClick={() => canManageTracker && deleteTracker(selectedTracker.id)}
            disabled={!canManageTracker}
            title={!canManageTracker ? 'Лише власник може це зробити' : 'Видаляє також усю історію'}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
              canManageTracker
                ? 'border border-gray-200 bg-white text-rose-600 hover:bg-rose-50'
                : 'cursor-not-allowed border border-stone-200 bg-stone-100 text-stone-400'
            }`}
          >
            <Trash2 size={16} /> Видалити
          </button>
        </div>
      </div>
    </header>
  );
}

export default TrackerHeader;
