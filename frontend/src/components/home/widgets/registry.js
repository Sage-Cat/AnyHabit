import {
  Activity,
  BarChart3,
  CalendarRange,
  Code2,
  Coins,
  Flame,
  Gauge,
  Grid3x3,
  Layers,
  LineChart,
  MonitorPlay,
  NotebookPen,
  Smile,
  Sparkles,
  Target,
  Zap
} from 'lucide-react';
import { toSafeNumber } from './helpers';

export const WIDGET_DEFINITIONS = {
  cultivationStats: {
    label: 'Загальна статистика',
    icon: Gauge,
    description: 'Усі звички разом: сьогодні, 7 і 30 днів, дні без порушень, попередження.',
    defaultSize: { w: 8, h: 7, minW: 4, minH: 5 },
    defaultConfig: {}
  },
  cultivationChart: {
    label: 'Графік усіх звичок',
    icon: LineChart,
    description: 'Кожна звичка своїм кольором і всі разом: частка успішних днів.',
    defaultSize: { w: 7, h: 10, minW: 4, minH: 7 },
    defaultConfig: { days: 30 }
  },
  cultivationHeatmap: {
    label: 'Загальна теплова карта',
    icon: Grid3x3,
    description: 'Кожен день за 24 тижні: скільки звичок виконано.',
    defaultSize: { w: 5, h: 7, minW: 3, minH: 6 },
    defaultConfig: {}
  },
  impactSummary: {
    label: 'Підсумки впливу',
    icon: Coins,
    description: 'Сумарний вплив за вибраними звичками.',
    defaultSize: { w: 7, h: 10, minW: 4, minH: 6 },
    defaultConfig: { autoSelect: true, selectedTrackerIds: [] }
  },
  trackerOverview: {
    label: 'Огляд звичок',
    icon: Activity,
    description: 'Статистика активних звичок з першого погляду.',
    defaultSize: { w: 5, h: 6, minW: 3, minH: 5 },
    defaultConfig: {}
  },
  categoryBreakdown: {
    label: 'Розподіл за категоріями',
    icon: Layers,
    description: 'Розподіл звичок за категоріями.',
    defaultSize: { w: 5, h: 6, minW: 3, minH: 4 },
    defaultConfig: {}
  },
  topImpact: {
    label: 'Найбільший вплив',
    icon: BarChart3,
    description: 'Звички за орієнтовним місячним впливом.',
    defaultSize: { w: 6, h: 6, minW: 3, minH: 4 },
    defaultConfig: {}
  },
  todayFocus: {
    label: 'Фокус на сьогодні',
    icon: Target,
    description: 'Що ще потрібно зробити в поточному періоді.',
    defaultSize: { w: 6, h: 8, minW: 3, minH: 5 },
    defaultConfig: {}
  },
  streaks: {
    label: 'Активні серії',
    icon: Flame,
    description: 'Ваші найдовші серії просто зараз.',
    defaultSize: { w: 6, h: 7, minW: 3, minH: 4 },
    defaultConfig: {}
  },
  trackerSpotlight: {
    label: 'Звичка в центрі уваги',
    icon: Sparkles,
    description: 'Одна звичка зблизька з кнопкою запису в один дотик.',
    defaultSize: { w: 4, h: 11, minW: 3, minH: 9 },
    defaultConfig: { trackerId: null }
  },
  quickLog: {
    label: 'Швидкий запис',
    icon: Zap,
    description: 'Запис в один дотик для звичок, які ви ведете найчастіше.',
    defaultSize: { w: 5, h: 8, minW: 3, minH: 4 },
    defaultConfig: { trackerIds: [] }
  },
  heatmap: {
    label: 'Теплова карта регулярності',
    icon: CalendarRange,
    description: 'Останні 24 тижні однієї звички з першого погляду.',
    defaultSize: { w: 6, h: 8, minW: 4, minH: 6 },
    defaultConfig: { trackerId: null }
  },
  activityFeed: {
    label: 'Остання активність',
    icon: Activity,
    description: 'Найновіші записи за всіма звичками.',
    defaultSize: { w: 5, h: 10, minW: 3, minH: 5 },
    defaultConfig: {}
  },
  journalFeed: {
    label: 'Стрічка щоденника',
    icon: NotebookPen,
    description: 'Ваші найновіші записи щоденника, де б ви їх не залишили.',
    defaultSize: { w: 5, h: 10, minW: 3, minH: 5 },
    defaultConfig: {}
  },
  moodTrend: {
    label: 'Динаміка настрою',
    icon: Smile,
    description: 'Середній настрій із записів щоденника з часом.',
    defaultSize: { w: 6, h: 8, minW: 3, minH: 5 },
    defaultConfig: {}
  },
  notes: {
    label: 'Нотатки',
    icon: NotebookPen,
    description: 'Довільна нотатка, закріплена на головній.',
    defaultSize: { w: 4, h: 7, minW: 2, minH: 3 },
    defaultConfig: { text: '' }
  },
  apiExplorer: {
    label: 'Огляд API',
    icon: Code2,
    description: 'Готові до копіювання приклади запитів до вашого екземпляра.',
    defaultSize: { w: 6, h: 11, minW: 4, minH: 9 },
    defaultConfig: { path: '/trackers/', snippet: 'curl' }
  },
  embed: {
    label: 'Вбудована сторінка',
    icon: MonitorPlay,
    description: 'Показати іншу сторінку — панель Grafana, дошку статусу.',
    defaultSize: { w: 6, h: 10, minW: 3, minH: 5 },
    defaultConfig: { url: '', title: '' }
  }
};

/** Default titles from before the UI was translated; shown under their new names. */
const LEGACY_TITLES = {
  impactSummary: 'Impact Totals',
  trackerOverview: 'Tracker Overview',
  categoryBreakdown: 'Category Breakdown',
  topImpact: 'Top Impact Rates',
  todayFocus: "Today's Focus",
  streaks: 'Active Streaks',
  trackerSpotlight: 'Tracker Spotlight',
  quickLog: 'Quick Log',
  heatmap: 'Consistency Heatmap',
  activityFeed: 'Recent Activity',
  journalFeed: 'Journal Feed',
  moodTrend: 'Mood Trend',
  notes: 'Notes',
  apiExplorer: 'API Explorer',
  embed: 'Embed'
};

export const WIDGET_TYPE_ALIASES = {
  finance: 'impactSummary'
};

export const WIDGET_TYPES = Object.keys(WIDGET_DEFINITIONS);

// Widgets served by /dashboard/activity rather than /dashboard/summary.
export const ACTIVITY_WIDGET_TYPES = new Set(['activityFeed', 'journalFeed', 'moodTrend']);

// Widgets served by /cultivation/stats: every habit together.
export const STATS_WIDGET_TYPES = new Set(['cultivationStats', 'cultivationChart', 'cultivationHeatmap']);

export const createWidgetId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export const normalizeImpactConfig = (config) => {
  const base = config && typeof config === 'object' ? config : {};

  return {
    autoSelect: base.autoSelect !== false,
    selectedTrackerIds: Array.isArray(base.selectedTrackerIds)
      ? [...new Set(base.selectedTrackerIds.map((id) => toSafeNumber(id)).filter((id) => id > 0))]
      : []
  };
};

export const normalizeWidget = (rawWidget) => {
  if (!rawWidget || typeof rawWidget !== 'object') return null;

  const rawType = typeof rawWidget.type === 'string' ? rawWidget.type : '';
  const resolvedType = WIDGET_TYPE_ALIASES[rawType] || rawType;
  const definition = WIDGET_DEFINITIONS[resolvedType];
  if (!definition) return null;

  const id =
    typeof rawWidget.id === 'string' && rawWidget.id.trim() ? rawWidget.id : `${resolvedType}-${createWidgetId()}`;
  const title =
    typeof rawWidget.title === 'string' &&
    rawWidget.title.trim() &&
    rawWidget.title.trim() !== LEGACY_TITLES[resolvedType]
      ? rawWidget.title.trim()
      : definition.label;

  const config =
    resolvedType === 'impactSummary'
      ? normalizeImpactConfig(rawWidget.config)
      : rawWidget.config && typeof rawWidget.config === 'object'
        ? { ...rawWidget.config }
        : { ...definition.defaultConfig };

  return {
    id,
    type: resolvedType,
    title,
    config
  };
};

export const normalizeWidgets = (rawWidgets) => {
  if (!Array.isArray(rawWidgets)) return [];

  return rawWidgets
    .map(normalizeWidget)
    .filter(Boolean)
    .map((widget, index) => {
      if (index === 0) return widget;
      return {
        ...widget,
        id: widget.id || `${widget.type}-${createWidgetId()}`
      };
    });
};

export const getSelectedImpactTrackerIds = (widget, trackerMap, candidateIds) => {
  const config = normalizeImpactConfig(widget.config);

  if (config.autoSelect) {
    return candidateIds;
  }

  return config.selectedTrackerIds.filter((trackerId) => !!trackerMap[trackerId]);
};
