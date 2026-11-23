import { Archive, ChevronDown, Download, Home, Plus, Search, Settings, Sprout, Upload, Users, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { fetchHabitsApi } from '../services/cultivationApi';
import { TRACKER_COLOR_HEX } from '../constants/tracker';
import { useAppState } from '../state/appState';
import { categoryLabel } from '../utils/tracker';

const TABS = [
  { id: 'active', label: 'Активні' },
  { id: 'all', label: 'Усі' }
];

/** A habit in progress: neither paused nor archived. */
const isActiveTracker = (tracker) => tracker.is_active && !tracker.archived_at;

function Sidebar({ isHomeActive, isPracticeActive }) {
  const navigate = useNavigate();
  const {
    isSidebarOpen,
    setIsSidebarOpen,
    visibleTrackers,
    sortedCategoryEntries,
    activeCategory,
    archivedCount,
    showArchived,
    setShowArchived,
    collapsedCategories,
    setCollapsedCategories,
    selectedTrackerId,
    openTrackerModal,
    setIsSettingsOpen,
    setIsExportOpen,
    setIsImportOpen,
    setIsGroupManagementOpen,
    setIsCommandPaletteOpen,
    setSelectedCategory,
    setSelectedTrackerId
  } = useAppState();

  const [trackerTab, setTrackerTab] = useState('active');
  const [query, setQuery] = useState('');
  const { pathname } = useLocation();
  const [failedTrackerIds, setFailedTrackerIds] = useState(() => new Set());
  const [habitsVersion, setHabitsVersion] = useState(0);

  // Trackers whose cultivated habit failed its formation and awaits a decision.
  // Refetched on navigation and when the habit page announces a change.
  useEffect(() => {
    const onChanged = () => setHabitsVersion((value) => value + 1);
    window.addEventListener('habits-changed', onChanged);
    return () => window.removeEventListener('habits-changed', onChanged);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchHabitsApi()
      .then((habits) => {
        if (cancelled) return;
        setFailedTrackerIds(
          new Set(
            habits
              .filter((habit) => habit.attempt?.failed_on && !habit.paused && habit.tracker?.id)
              .map((habit) => habit.tracker.id)
          )
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pathname, habitsVersion]);

  const openHome = () => {
    setSelectedTrackerId(null);
    setSelectedCategory(null);
    setIsSidebarOpen(false);
    navigate('/');
  };

  const openPractice = () => {
    setSelectedTrackerId(null);
    setSelectedCategory(null);
    setIsSidebarOpen(false);
    navigate('/practice');
  };

  const openCategory = (category) => {
    setSelectedCategory(category);
    setSelectedTrackerId(null);
    setIsSidebarOpen(false);
    navigate(`/category/${encodeURIComponent(category)}`);
  };

  const openTracker = (trackerId, category) => {
    if (category) setSelectedCategory(category);
    setSelectedTrackerId(trackerId);
    setIsSidebarOpen(false);
    navigate(`/tracker/${trackerId}`);
  };

  const tabCounts = { active: visibleTrackers.filter(isActiveTracker).length, all: visibleTrackers.length };

  const filteredEntries = useMemo(() => {
    const search = query.trim().toLowerCase();

    const matchesTab = (tracker) => trackerTab === 'all' || isActiveTracker(tracker);

    const matchesQuery = (tracker) =>
      !search || tracker.name.toLowerCase().includes(search) || (tracker.category || '').toLowerCase().includes(search);

    return sortedCategoryEntries
      .map(([category, items]) => [category, items.filter((item) => matchesTab(item) && matchesQuery(item))])
      .filter(([, items]) => items.length > 0);
  }, [sortedCategoryEntries, trackerTab, query]);

  const hasResults = filteredEntries.length > 0;

  return (
    <div
      className={`app-sidebar fixed inset-y-0 left-0 z-50 flex w-72 transform flex-col border-r border-gray-100 bg-white p-6 transition-transform duration-300 md:relative md:translate-x-0 ${
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="mb-6 flex items-center justify-between">
        <button
          type="button"
          onClick={openHome}
          className="flex items-center gap-3 rounded-xl px-1 py-1 transition-colors hover:bg-stone-50"
        >
          <img src="/AnyHabit.png" alt="" className="h-8 w-8 rounded-lg object-cover" />
          <span className="text-xl font-bold tracking-tight">AnyHabit</span>
        </button>
        <button
          className="text-gray-400 hover:text-stone-900 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-label="Закрити навігацію"
        >
          <X size={20} />
        </button>
      </div>

      <button
        type="button"
        onClick={() => {
          setIsSidebarOpen(false);
          setIsCommandPaletteOpen(true);
        }}
        className="mb-4 flex w-full items-center gap-2 rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-400 transition-colors hover:border-stone-300 hover:text-stone-600"
      >
        <Search size={15} />
        <span className="flex-1 text-left">Пошук…</span>
        <kbd className="rounded border border-gray-200 px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
      </button>

      <button
        type="button"
        onClick={openHome}
        className={`mb-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
          isHomeActive ? 'bg-stone-100 text-stone-900' : 'text-gray-500 hover:bg-gray-100 hover:text-stone-800'
        }`}
      >
        <Home size={16} />
        <span>Головна</span>
      </button>

      <button
        type="button"
        onClick={openPractice}
        className={`mb-6 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
          isPracticeActive ? 'bg-stone-100 text-stone-900' : 'text-gray-500 hover:bg-gray-100 hover:text-stone-800'
        }`}
      >
        <Sprout size={16} />
        <span>Культивація</span>
      </button>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">Звички</h2>
        <button
          onClick={() => openTrackerModal()}
          className="flex items-center justify-center text-gray-400 transition-colors hover:text-stone-900"
          aria-label="Нова звичка"
        >
          <Plus size={18} />
        </button>
      </div>

      {visibleTrackers.length > 0 && (
        <>
          <div className="mb-3 flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setTrackerTab(tab.id)}
                aria-pressed={trackerTab === tab.id}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  trackerTab === tab.id ? 'bg-stone-900 text-white' : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                {tab.label} ({tabCounts[tab.id]})
              </button>
            ))}
          </div>

          {/* Filtering the list in place beats scrolling once you keep more
              than a handful of trackers. */}
          <div className="relative mb-3">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <label htmlFor="sidebar-filter" className="sr-only">
              Фільтр звичок
            </label>
            <input
              id="sidebar-filter"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Фільтр…"
              className="w-full rounded-lg border border-gray-200 bg-stone-50 py-1.5 pl-8 pr-2 text-xs outline-none focus:border-stone-400"
            />
          </div>
        </>
      )}

      <ul className="flex-1 space-y-4 overflow-y-auto pr-1">
        {!hasResults ? (
          <li className="mt-6 text-center text-sm text-gray-400">
            {query
              ? 'Жодна звичка не підходить під фільтр.'
              : visibleTrackers.length
                ? 'Активних звичок немає.'
                : 'Звичок ще немає.'}
          </li>
        ) : (
          filteredEntries.map(([category, items]) => (
            <li key={category} className="pb-1">
              <div
                className={`mb-2 flex items-center gap-1 rounded-lg px-1 py-0.5 transition-colors ${
                  activeCategory === category ? 'bg-stone-50' : ''
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    openCategory(category);
                    setCollapsedCategories((previous) => ({ ...previous, [category]: false }));
                  }}
                  className="flex min-w-0 flex-1 items-center justify-between rounded-md px-1.5 py-1.5 text-left transition-colors hover:bg-stone-100/60"
                >
                  <span className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-stone-500">
                    {categoryLabel(category)}
                  </span>
                  <span className="category-count-badge ml-2 rounded-full bg-stone-100/80 px-2 py-0.5 text-[10px] font-medium text-stone-400">
                    {items.length}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCollapsedCategories((previous) => ({ ...previous, [category]: !previous[category] }))
                  }
                  className="flex h-7 w-7 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-stone-100/70 hover:text-stone-700"
                  aria-label={`${collapsedCategories[category] ? 'Розгорнути' : 'Згорнути'} ${categoryLabel(category)}`}
                  aria-expanded={!collapsedCategories[category]}
                >
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${collapsedCategories[category] ? '-rotate-90' : ''}`}
                  />
                </button>
              </div>

              {!collapsedCategories[category] && (
                <ul className="ml-2 space-y-1 border-l border-stone-200/70 pl-4 pr-1">
                  {items.map((tracker) => {
                    const accent = TRACKER_COLOR_HEX[tracker.color];
                    const attemptFailed = failedTrackerIds.has(tracker.id);

                    return (
                      <li key={tracker.id}>
                        <button
                          type="button"
                          onClick={() => openTracker(tracker.id, category)}
                          data-testid={attemptFailed ? 'attempt-failed' : undefined}
                          title={attemptFailed ? 'Формування не вдалося — потрібне рішення' : undefined}
                          aria-label={
                            attemptFailed ? `${tracker.name}. Формування не вдалося — потрібне рішення` : undefined
                          }
                          className={`flex w-full flex-col rounded-lg px-2.5 py-2 text-left transition-all ${
                            attemptFailed
                              ? `bg-rose-50 font-medium text-rose-700 ${
                                  selectedTrackerId === tracker.id ? 'ring-2 ring-rose-500' : ''
                                }`
                              : selectedTrackerId === tracker.id
                                ? 'bg-stone-100 font-medium text-stone-900'
                                : 'text-gray-500 hover:bg-stone-50 hover:text-stone-700'
                          }`}
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span className="flex min-w-0 items-center gap-2">
                              {accent && (
                                <span
                                  className="h-2 w-2 shrink-0 rounded-full"
                                  style={{ backgroundColor: accent }}
                                  aria-hidden="true"
                                />
                              )}
                              <span className="truncate">{tracker.name}</span>
                            </span>
                            <span className="flex shrink-0 items-center gap-1.5">
                              {tracker.archived_at && <Archive size={11} className="text-amber-500" />}
                              <span
                                className={`h-2 w-2 rounded-full ${
                                  tracker.archived_at
                                    ? 'bg-amber-400'
                                    : tracker.is_active
                                      ? 'bg-emerald-400'
                                      : 'bg-rose-400'
                                }`}
                                title={tracker.archived_at ? 'В архіві' : tracker.is_active ? 'Активна' : 'На паузі'}
                              />
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          ))
        )}
      </ul>

      {archivedCount > 0 && (
        <button
          type="button"
          onClick={() => {
            // Archived habits are never active: showing the archive shows every habit.
            if (!showArchived) setTrackerTab('all');
            setShowArchived(!showArchived);
          }}
          aria-pressed={showArchived}
          className={`mt-3 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
            showArchived ? 'bg-stone-100 text-stone-800' : 'text-gray-500 hover:bg-gray-100 hover:text-stone-800'
          }`}
        >
          <Archive size={16} />
          <span className="flex-1 text-left">{showArchived ? 'Сховати архів' : 'Показати архів'}</span>
          <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-medium text-stone-500">
            {archivedCount}
          </span>
        </button>
      )}

      <div className="mt-3 space-y-1 border-t border-gray-100 pt-3">
        {[
          { label: 'Групи', Icon: Users, action: () => setIsGroupManagementOpen(true) },
          { label: 'Експорт даних', Icon: Download, action: () => setIsExportOpen(true) },
          { label: 'Відновити з копії', Icon: Upload, action: () => setIsImportOpen(true) },
          { label: 'Налаштування', Icon: Settings, action: () => setIsSettingsOpen(true) }
        ].map((item) => (
          <button
            key={item.label}
            onClick={() => {
              item.action();
              setIsSidebarOpen(false);
            }}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-stone-800"
          >
            <item.Icon size={16} />
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default Sidebar;
