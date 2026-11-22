import { ArrowLeft, Check, HelpCircle, Menu, Minus, Moon, User, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  archiveHabitApi,
  changeLevelApi,
  changeStageApi,
  createVersionApi,
  endModeApi,
  fetchHabitApi,
  fetchOverviewApi,
  markDayApi,
  startModeApi,
  startNewAttemptApi,
  unarchiveHabitApi
} from '../../services/cultivationApi';
import { useAppState } from '../../state/appState';
import { pluralCount } from '../../utils/plural';
import { formatDateTime } from '../../utils/date';
import LevelFields from './LevelFields';
import { buildLevel, hasLevelValue, levelFromSpec, levelKeys } from './levelHelpers';
import SleepEntryModal from './SleepEntryModal';
import { DayStatusPill, Field, LevelBadge, ModeBadge, StageBadge } from './common';
import {
  BUTTON_PRIMARY,
  BUTTON_SECONDARY,
  CARD_CLASS,
  DAY_STATUS_LABELS,
  DAY_STATUS_STYLES,
  INPUT_CLASS,
  KIND_LABELS,
  STAGE_OPTIONS,
  WARNING_LABEL,
  WARNING_STYLE,
  dayLabel,
  dayStyle,
  formatDay,
  formatDays,
  formatHabitDay,
  formatPercent
} from './helpers';

const todayIso = () => {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

function Section({ title, children, testId, className = '' }) {
  return (
    <section className={`${CARD_CLASS} min-w-0 ${className}`} data-testid={testId}>
      <h2 className="mb-3 text-base font-bold text-stone-900">{title}</h2>
      {children}
    </section>
  );
}

// untested / manual must never look like a pass, so each status has its own mark.
const CRITERION_VIEW = {
  met: { Icon: Check, text: 'виконано', tone: 'text-emerald-700 bg-emerald-50' },
  not_met: { Icon: X, text: 'не виконано', tone: 'text-rose-700 bg-rose-50' },
  insufficient: { Icon: Minus, text: 'мало даних', tone: 'text-stone-500 bg-stone-100' },
  untested: { Icon: HelpCircle, text: 'не перевірено', tone: 'text-amber-800 bg-amber-50' },
  manual: { Icon: User, text: 'оцінюєте ви', tone: 'text-sky-700 bg-sky-50' }
};

function IntegrationList({ integration }) {
  if (!integration) return <p className="text-sm text-gray-400">Критерії інтеграції для цього етапу не задані.</p>;
  return (
    <div>
      <p className="mb-3 text-sm text-gray-600">
        Вікно: {pluralCount(integration.window_days, ['день', 'дні', 'днів'])}
        {integration.since && ` (з ${formatDay(integration.since)})`}.{' '}
        {integration.ready ? 'Усі автоматичні умови виконано.' : 'Не всі умови виконано.'}
      </p>
      <ul className="space-y-2">
        {integration.criteria.map((criterion) => {
          const view = CRITERION_VIEW[criterion.status] || CRITERION_VIEW.insufficient;
          return (
            <li
              key={criterion.key}
              data-status={criterion.status}
              className="flex flex-wrap items-start gap-3 rounded-xl border border-gray-100 p-3"
            >
              <span
                className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${view.tone}`}
              >
                <view.Icon size={12} aria-hidden="true" />
                {view.text}
              </span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-medium text-stone-800">{criterion.label}</p>
                {(criterion.required != null || criterion.actual != null) && (
                  <p className="text-xs text-gray-500">
                    Потрібно: {String(criterion.required ?? '—')} · Зараз: {String(criterion.actual ?? '—')}
                  </p>
                )}
                {criterion.note && <p className="mt-0.5 text-xs text-gray-500">{criterion.note}</p>}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Calendar({ days, kind, onPick }) {
  if (!days?.length) return null;
  // Monday-first grid, padded so each column is a weekday.
  const first = days[0].date.split('-').map(Number);
  const offset = (new Date(first[0], first[1] - 1, first[2]).getDay() + 6) % 7;
  return (
    <div className="max-w-md">
      <div className="mb-1 grid grid-cols-7 gap-1 text-center text-[10px] uppercase text-gray-400">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'].map((name) => (
          <span key={name}>{name}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1" data-testid="day-calendar">
        {Array.from({ length: offset }, (_, index) => (
          <span key={`pad-${index}`} />
        ))}
        {days.map((day) => {
          const label = `${formatHabitDay(kind, day.date)} — ${dayLabel(day)}`;
          const [year, month, date] = day.date.split('-').map(Number);
          return (
            <button
              key={day.date}
              type="button"
              title={label}
              aria-label={label}
              data-status={day.status}
              data-warning={day.warning ? 'true' : undefined}
              onClick={() => onPick(day)}
              className={`flex aspect-square items-center justify-center rounded-md text-[10px] ${dayStyle(day)} ${
                ['success', 'fail', 'invalid'].includes(day.status) ? 'text-white' : 'text-stone-700'
              }`}
            >
              {/* A sleep day is the night before it. */}
              {kind === 'sleep' ? `${new Date(year, month - 1, date - 1).getDate()}–${date}` : date}
            </button>
          );
        })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        {Object.entries(DAY_STATUS_LABELS).map(([status, text]) => (
          <li key={status} className="flex items-center gap-1.5">
            <span className={`h-3 w-3 rounded-[3px] ${DAY_STATUS_STYLES[status]}`} /> {text}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className={`h-3 w-3 rounded-[3px] ${WARNING_STYLE}`} /> {WARNING_LABEL}
        </li>
      </ul>
    </div>
  );
}

function Rates({ rates }) {
  const items = [
    { key: '7', title: '7 днів' },
    { key: '30', title: '30 днів' },
    { key: 'integration', title: 'Вікно інтеграції' }
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map(({ key, title }) => {
        const rate = rates?.[key];
        return (
          <div key={key} className="rounded-xl bg-stone-50 p-3">
            <p className="text-[11px] uppercase tracking-wider text-gray-400">
              {title}
              {key === 'integration' && rate ? ` (${rate.window_days} дн.)` : ''}
            </p>
            <p className="mt-0.5 text-xl font-bold text-stone-900">{formatPercent(rate?.success_rate)}</p>
            <p className="text-xs text-gray-500">
              З урахуванням мінімуму: {formatPercent(rate?.acceptable_rate)}
              {rate && ` · спостережень: ${rate.observed_days}`}
              {rate?.warnings > 0 && ` · з попередженням: ${rate.warnings}`}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function Recovery({ recovery, episodes }) {
  if (!recovery) return null;
  const dev = recovery.current_deviation;
  const rows = [
    ['Поточне відхилення', dev ? pluralCount(dev.ongoing_days ?? dev.fail_days ?? 0, ['день', 'дні', 'днів']) : '—'],
    ['Медіана до першого ОК', formatDays(recovery.first_ok_median)],
    ['Медіана до підтвердження', formatDays(recovery.confirmed_median)],
    ['Частка вчасних відновлень', formatPercent(recovery.in_term_share)],
    [
      'Найдовше відхилення',
      recovery.longest_deviation_days != null
        ? pluralCount(recovery.longest_deviation_days, ['день', 'дні', 'днів'])
        : '—'
    ]
  ];
  return (
    <div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[11px] uppercase tracking-wider text-gray-400">{label}</dt>
            <dd className="text-sm font-semibold text-stone-800">{value}</dd>
          </div>
        ))}
      </dl>
      {episodes?.length > 0 ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-sm" data-testid="episodes-table">
            <thead className="text-xs uppercase tracking-wider text-gray-400">
              <tr>
                <th className="py-1 pr-3 font-medium">Початок</th>
                <th className="py-1 pr-3 font-medium">Днів невдачі</th>
                <th className="py-1 pr-3 font-medium">До першого ОК</th>
                <th className="py-1 pr-3 font-medium">До підтвердження</th>
                <th className="py-1 font-medium">Причини</th>
              </tr>
            </thead>
            <tbody>
              {episodes.map((episode) => (
                <tr key={episode.start} className="border-t border-gray-100 align-top">
                  <td className="py-1.5 pr-3">{formatDay(episode.start)}</td>
                  <td className="py-1.5 pr-3">{episode.fail_days}</td>
                  <td className="py-1.5 pr-3">{episode.days_to_first_ok ?? '—'}</td>
                  <td className="py-1.5 pr-3">
                    {episode.confirmed
                      ? (episode.days_to_confirmed ?? '—')
                      : episode.ongoing_days != null
                        ? `триває (${episode.ongoing_days})`
                        : '—'}
                  </td>
                  <td className="py-1.5 text-gray-500">{episode.reasons?.length ? episode.reasons.join('; ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-sm text-gray-400">Епізодів відхилення ще не було.</p>
      )}
    </div>
  );
}

function Passport({ habit }) {
  const spec = habit.passport || {};
  const unit = spec.unit || habit.tracker?.unit || '';
  const rows = [
    ['Назва', spec.name],
    ['Тип', KIND_LABELS[habit.kind] || habit.kind],
    ['Етап', habit.stage_label],
    ['Вимога', habit.today?.requirement],
    ['Мінімум', habit.today?.minimum || (spec.minimum ? null : '—')],
    ['Допуск (з попередженням)', habit.today?.tolerance || '—'],
    ['Одиниця', habit.kind === 'build' ? unit || '—' : null],
    ['Пріоритет', spec.priority != null ? String(spec.priority) : null],
    ['Опис', spec.description || null]
  ].filter(([, value]) => value != null);
  // A ladder replaces the legacy subgoals in the view.
  const subgoals = spec.levels?.length ? [] : spec.subgoals || [];
  return (
    <div>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2" data-testid="passport-view">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[11px] uppercase tracking-wider text-gray-400">{label}</dt>
            <dd className="text-sm text-stone-800">{value}</dd>
          </div>
        ))}
      </dl>
      {subgoals.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-wider text-gray-400">Підцілі</p>
          <ul className="mt-1 list-inside list-disc text-sm text-stone-800">
            {subgoals.map((goal, index) => (
              <li key={`${goal.name}-${index}`}>
                {goal.name}:{' '}
                {Object.entries(goal.level || {})
                  .map(([k, v]) => `${k} ${v}`)
                  .join(', ') || '—'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LevelsBlock({ habit, onChanged }) {
  const { notify } = useAppState();
  const ladder = habit.ladder;
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const hasLadder = ladder.count > 1 || habit.passport?.levels?.length > 0;
  const changes = (habit.level_changes || []).slice(-5).reverse();

  const change = async (direction) => {
    if (!reason.trim()) {
      setError('Вкажіть причину зміни рівня');
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      await changeLevelApi(habit.id, { direction, reason: reason.trim() });
      notify.success(direction === 'up' ? 'Рівень підвищено' : 'Рівень знижено');
      setReason('');
      await onChanged();
    } catch (changeError) {
      setError(changeError?.message || 'Не вдалося змінити рівень');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      {ladder.levels?.length > 0 ? (
        <ol className="space-y-2" data-testid="ladder-levels">
          {ladder.levels.map((rung) => (
            <li
              key={rung.number}
              data-testid="ladder-level"
              data-current={rung.current ? 'true' : undefined}
              className={`rounded-xl border p-3 text-sm ${
                rung.current ? 'border-emerald-300 bg-emerald-50' : 'border-gray-100'
              }`}
            >
              <p className="flex flex-wrap items-center gap-2 font-semibold text-stone-900">
                Рівень {rung.number}
                {rung.name && <span className="font-medium text-stone-700">— {rung.name}</span>}
                {rung.current && (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                    поточний
                  </span>
                )}
              </p>
              <p className="text-stone-800">Вимога: {rung.requirement || '—'}</p>
              {rung.tolerance && <p className="text-xs text-amber-700">Допуск з попередженням: {rung.tolerance}</p>}
              {rung.minimum && <p className="text-xs text-gray-500">Мінімум: {rung.minimum}</p>}
            </li>
          ))}
        </ol>
      ) : null}
      {!hasLadder && levelKeys(habit.kind).length > 0 && (
        <p className="mt-2 text-sm text-gray-500">Поки один рівень. Драбину рівнів можна додати в паспорті.</p>
      )}
      {hasLadder && !habit.archived && (
        <div className="mt-4 space-y-3" data-testid="level-form">
          <input
            type="text"
            aria-label="Причина зміни рівня"
            placeholder="Причина"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={INPUT_CLASS}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={isSaving || !ladder.can_upgrade}
              onClick={() => change('up')}
              className={BUTTON_SECONDARY}
            >
              Підвищити рівень
            </button>
            <button
              type="button"
              disabled={isSaving || !ladder.can_downgrade}
              onClick={() => change('down')}
              className={BUTTON_SECONDARY}
            >
              Знизити рівень
            </button>
          </div>
          <p className="text-xs text-gray-500" data-testid="upgrade-note">
            Після підвищення звичка почне формування нового рівня з дня підвищення, а в ранзі й далі рахуватиметься на
            рівні {ladder.current}.
          </p>
          {habit.rank_level >= 1 && (
            <p className="text-xs text-gray-500" data-testid="rank-level-note">
              У ранзі: рівень {habit.rank_level}
            </p>
          )}
          {!ladder.can_upgrade && ladder.upgrade_blocker && (
            <p className="text-xs text-gray-500" data-testid="upgrade-blocker">
              {ladder.upgrade_blocker}
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm text-rose-600">
              {error}
            </p>
          )}
        </div>
      )}
      {changes.length > 0 && (
        <ul className="mt-4 divide-y divide-gray-100 rounded-xl border border-gray-100" data-testid="level-changes">
          {changes.map((item, index) => (
            <li key={`${item.date}-${index}`} className="px-3 py-2 text-sm text-gray-600">
              <span className="font-medium text-stone-800">
                {formatDay(item.date)}: рівень {item.from} → {item.to}
              </span>
              {item.reason && ` — ${item.reason}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function VersionHistory({ versions }) {
  if (!versions?.length) return null;
  const ordered = [...versions].sort((a, b) => (b.effective_from + b.id).localeCompare(a.effective_from + a.id));
  return (
    <ul className="mt-4 divide-y divide-gray-100 rounded-xl border border-gray-100" data-testid="version-history">
      {ordered.map((version) => (
        <li key={version.id} className="px-3 py-2 text-sm">
          <span className="font-medium text-stone-800">
            з {formatDay(version.effective_from, { day: 'numeric', month: 'short', year: 'numeric' })}
          </span>
          <span className="ml-2 text-xs text-gray-500">
            {version.author === 'api' ? 'API' : 'ви'} · записано {formatDateTime(version.created_at)}
          </span>
          <p className="text-gray-600">{version.reason || 'без причини'}</p>
        </li>
      ))}
    </ul>
  );
}

const rungFromSpec = (rung) => ({
  name: rung?.name ?? '',
  level: levelFromSpec(rung?.level),
  tolerance: levelFromSpec(rung?.tolerance),
  minimum: levelFromSpec(rung?.minimum)
});

function EditPassport({ habit, onSaved }) {
  const { notify } = useAppState();
  const spec = habit.passport || {};
  const latestEffective = (habit.versions || []).reduce(
    (max, v) => (v.effective_from > max ? v.effective_from : max),
    ''
  );
  const [open, setOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('');
  const [level, setLevel] = useState(levelFromSpec());
  const [minimum, setMinimum] = useState(levelFromSpec());
  const [tolerance, setTolerance] = useState(levelFromSpec());
  const [rungs, setRungs] = useState([]);
  const [json, setJson] = useState('');
  const [reason, setReason] = useState('');
  const [effectiveFrom, setEffectiveFrom] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const openForm = () => {
    setName(spec.name || '');
    setUnit(spec.unit || '');
    setLevel(levelFromSpec(spec.level));
    setMinimum(levelFromSpec(spec.minimum));
    setTolerance(levelFromSpec(spec.tolerance));
    setRungs((spec.levels || []).map(rungFromSpec));
    setJson(JSON.stringify(spec, null, 2));
    setReason('');
    setEffectiveFrom('');
    setError('');
    setAdvanced(false);
    setOpen(true);
  };

  if (!open) {
    return (
      <button type="button" onClick={openForm} className={`${BUTTON_SECONDARY} mt-4`}>
        Редагувати паспорт
      </button>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    if (!reason.trim()) {
      setError('Вкажіть причину зміни');
      return;
    }
    const payload = { reason: reason.trim() };
    if (effectiveFrom) payload.effective_from = effectiveFrom;

    if (advanced) {
      try {
        const parsed = JSON.parse(json);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('not an object');
        payload.spec = parsed;
      } catch {
        setError('JSON паспорта некоректний');
        return;
      }
    } else {
      if (!name.trim()) {
        setError('Назва не може бути порожньою');
        return;
      }
      const patch = { name: name.trim() };
      if (habit.kind === 'build') patch.unit = unit.trim();
      // With a ladder the current rung is the requirement: the server copies it to the passport.
      if (rungs.length === 0) {
        patch.level = buildLevel(habit.kind, level, { nulls: true });
        if (hasLevelValue(habit.kind, minimum)) patch.minimum = buildLevel(habit.kind, minimum, { nulls: true });
        else if (spec.minimum) patch.minimum = null;
        if (hasLevelValue(habit.kind, tolerance)) patch.tolerance = buildLevel(habit.kind, tolerance, { nulls: true });
        else if (spec.tolerance) patch.tolerance = null;
      }
      if (levelKeys(habit.kind).length > 0) {
        if (rungs.length > 0) {
          for (const [index, rung] of rungs.entries()) {
            if (!hasLevelValue(habit.kind, rung.level)) {
              setError(`Рівень ${index + 1}: вкажіть вимогу`);
              return;
            }
          }
          patch.levels = rungs.map((rung) => {
            const out = {};
            if (rung.name.trim()) out.name = rung.name.trim();
            out.level = buildLevel(habit.kind, rung.level);
            if (hasLevelValue(habit.kind, rung.tolerance)) out.tolerance = buildLevel(habit.kind, rung.tolerance);
            if (hasLevelValue(habit.kind, rung.minimum)) out.minimum = buildLevel(habit.kind, rung.minimum);
            return out;
          });
          // A new ladder starts at level 1; an existing one keeps its level (moves go through /level).
          if (!spec.levels) patch.current_level = 1;
        } else if (spec.levels) {
          patch.levels = null;
          patch.current_level = null;
        }
      }
      payload.patch = patch;
    }

    setIsSaving(true);
    setError('');
    try {
      await createVersionApi(habit.id, payload);
      notify.success('Створено нову версію паспорта');
      setOpen(false);
      onSaved();
    } catch (saveError) {
      setError(saveError?.message || 'Не вдалося зберегти паспорт');
    } finally {
      setIsSaving(false);
    }
  };

  const hasLevels = levelKeys(habit.kind).length > 0;
  const setRung = (index, key, value) =>
    setRungs((current) => current.map((rung, i) => (i === index ? { ...rung, [key]: value } : rung)));
  // The first rung starts from what the passport asks for now; later ones copy the previous rung.
  const createLadder = () => setRungs([{ name: '', level, tolerance, minimum }]);
  const addRung = () => setRungs((current) => [...current, { ...current.at(-1), name: '' }]);
  const removeRung = (index) => setRungs((current) => current.filter((_, i) => i !== index));
  // Removing the current rung or one below it would shift the habit to another level.
  const currentLevel = spec.levels ? spec.current_level || 1 : 1;

  return (
    <form
      onSubmit={submit}
      className="mt-4 space-y-4 rounded-xl border border-gray-200 p-4"
      data-testid="passport-form"
    >
      <label className="flex items-center gap-2 text-sm text-stone-700">
        <input type="checkbox" checked={advanced} onChange={(event) => setAdvanced(event.target.checked)} />
        Розширено: редагувати весь паспорт як JSON
      </label>
      {advanced ? (
        <textarea
          aria-label="JSON паспорта"
          value={json}
          onChange={(event) => setJson(event.target.value)}
          rows={14}
          className={`${INPUT_CLASS} font-mono text-xs`}
          spellCheck={false}
        />
      ) : (
        <>
          <Field label="Назва">
            <input
              type="text"
              aria-label="Назва"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          {hasLevels && rungs.length === 0 && <LevelFields kind={habit.kind} value={level} onChange={setLevel} />}
          {hasLevels && rungs.length > 0 && (
            <p className="text-sm text-gray-500" data-testid="ladder-requirement-note">
              Вимога, допуск і мінімум — ті, що в поточному рівні {currentLevel} драбини нижче.
            </p>
          )}
          {habit.kind === 'build' && (
            <Field label="Одиниця виміру">
              <input
                type="text"
                aria-label="Одиниця виміру"
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                className={INPUT_CLASS}
              />
            </Field>
          )}
          {hasLevels && rungs.length === 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Мінімум (порожньо — без мінімуму)
              </p>
              <LevelFields kind={habit.kind} prefix="Мінімум: " value={minimum} onChange={setMinimum} />
            </div>
          )}
          {hasLevels && rungs.length === 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
                Допуск: поза ціллю, але зараховується з попередженням (порожньо — без допуску)
              </p>
              <LevelFields kind={habit.kind} prefix="Допуск: " value={tolerance} onChange={setTolerance} />
            </div>
          )}
          {hasLevels && (
            <div className="space-y-3" data-testid="ladder-editor">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Рівні (необов'язково): вимога зростає від рівня до рівня
              </p>
              {rungs.map((rung, index) => {
                const n = index + 1;
                return (
                  <div key={n} className="space-y-3 rounded-xl border border-gray-100 p-3" data-testid="ladder-rung">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-stone-800">Рівень {n}</p>
                      {n > currentLevel && (
                        <button
                          type="button"
                          aria-label={`Прибрати рівень ${n}`}
                          onClick={() => removeRung(index)}
                          className={BUTTON_SECONDARY}
                        >
                          Прибрати
                        </button>
                      )}
                    </div>
                    <Field label="Назва рівня (необов'язково)">
                      <input
                        type="text"
                        aria-label={`Назва рівня ${n}`}
                        value={rung.name}
                        onChange={(event) => setRung(index, 'name', event.target.value)}
                        className={INPUT_CLASS}
                      />
                    </Field>
                    <LevelFields
                      kind={habit.kind}
                      prefix={`Рівень ${n}: `}
                      value={rung.level}
                      onChange={(value) => setRung(index, 'level', value)}
                    />
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Допуск рівня (порожньо — без допуску)
                    </p>
                    <LevelFields
                      kind={habit.kind}
                      prefix={`Рівень ${n}, допуск: `}
                      value={rung.tolerance}
                      onChange={(value) => setRung(index, 'tolerance', value)}
                    />
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Мінімум рівня (порожньо — без мінімуму)
                    </p>
                    <LevelFields
                      kind={habit.kind}
                      prefix={`Рівень ${n}, мінімум: `}
                      value={rung.minimum}
                      onChange={(value) => setRung(index, 'minimum', value)}
                    />
                  </div>
                );
              })}
              {rungs.length === 0 ? (
                <button type="button" onClick={createLadder} className={BUTTON_SECONDARY}>
                  Додати драбину рівнів
                </button>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={addRung} className={BUTTON_SECONDARY}>
                    Додати рівень
                  </button>
                  <button type="button" onClick={() => setRungs([])} className={BUTTON_SECONDARY}>
                    Прибрати драбину
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Причина зміни">
          <input
            type="text"
            aria-label="Причина зміни паспорта"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
        <Field
          label="Діє з"
          hint={
            latestEffective ? `Не раніше ${formatDay(latestEffective)}; порожньо — з сьогодні` : 'Порожньо — з сьогодні'
          }
        >
          <input
            type="date"
            aria-label="Діє з"
            min={latestEffective || undefined}
            value={effectiveFrom}
            onChange={(event) => setEffectiveFrom(event.target.value)}
            className={INPUT_CLASS}
          />
        </Field>
      </div>
      {error && (
        <p role="alert" className="text-sm text-rose-600">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={() => setOpen(false)} className={BUTTON_SECONDARY}>
          Скасувати
        </button>
        <button type="submit" disabled={isSaving} className={BUTTON_PRIMARY}>
          {isSaving ? 'Збереження…' : 'Зберегти нову версію'}
        </button>
      </div>
    </form>
  );
}

/** Small form: runs `action`, shows the error inline, calls `onDone`. */
function ActionForm({ title, children, submitLabel, onSubmit, testId }) {
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const handle = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError('');
    try {
      await onSubmit();
    } catch (actionError) {
      setError(actionError?.message || 'Не вдалося виконати дію');
    } finally {
      setIsSaving(false);
    }
  };
  return (
    <form onSubmit={handle} className="space-y-3" data-testid={testId}>
      <h3 className="text-sm font-semibold text-stone-800">{title}</h3>
      {children}
      {error && (
        <p role="alert" className="text-sm text-rose-600">
          {error}
        </p>
      )}
      <button type="submit" disabled={isSaving} className={BUTTON_SECONDARY}>
        {isSaving ? 'Виконується…' : submitLabel}
      </button>
    </form>
  );
}

/** Decision after a failed formation: a new attempt, or a step back to the previous level. */
function AttemptDecision({ habit, onDone }) {
  const { notify } = useAppState();
  const attempt = habit.attempt;
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const isFallback = attempt.action === 'fallback';

  const submit = async (event) => {
    event.preventDefault();
    if (!reason.trim()) {
      setError('Вкажіть причину');
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      if (isFallback) {
        await changeLevelApi(habit.id, { direction: 'down', reason: reason.trim() });
        notify.success('Рівень знижено');
      } else {
        await startNewAttemptApi(habit.id, { reason: reason.trim() });
        notify.success('Нову спробу розпочато');
      }
      setReason('');
      await onDone();
    } catch (actionError) {
      setError(actionError?.message || 'Не вдалося виконати дію');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section
      className="min-w-0 rounded-2xl border border-emerald-300 bg-emerald-50 p-5 shadow-sm xl:col-span-2"
      data-testid="attempt-decision"
    >
      <h2 className="mb-2 text-base font-bold text-stone-900">Формування не вдалося</h2>
      <p className="text-sm text-stone-800">
        За {attempt.days} дн. звичка не дійшла до стабілізації. Вирішіть, як продовжити.
      </p>
      {habit.today?.day?.detail && <p className="mt-1 text-xs text-gray-500">{habit.today.day.detail}</p>}
      <form onSubmit={submit} className="mt-3 space-y-3">
        <input
          type="text"
          aria-label="Причина рішення"
          placeholder="Причина"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className={INPUT_CLASS}
        />
        {error && (
          <p role="alert" className="text-sm text-rose-600">
            {error}
          </p>
        )}
        <button type="submit" disabled={isSaving} className={BUTTON_PRIMARY}>
          {isFallback ? `Повернутися на рівень ${attempt.fallback_level}` : 'Нова спроба'}
        </button>
      </form>
    </section>
  );
}

function HabitDetailPage() {
  const { habitId } = useParams();
  const navigate = useNavigate();
  const { setIsSidebarOpen, setSelectedTrackerId, setSelectedCategory, confirm, notify } = useAppState();
  const [habit, setHabit] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSleepOpen, setIsSleepOpen] = useState(false);
  const [timezone, setTimezone] = useState('');

  const [mark, setMark] = useState({ date: todayIso(), status: 'success', reason: '' });
  const [modeReason, setModeReason] = useState('');
  const [modeDate, setModeDate] = useState('');
  const [stageForm, setStageForm] = useState({ stage: 'formation', reason: '', effective_from: '' });

  useEffect(() => {
    setSelectedTrackerId(null);
    setSelectedCategory(null);
  }, [setSelectedCategory, setSelectedTrackerId]);

  const load = useCallback(async () => {
    try {
      const data = await fetchHabitApi(habitId, 90);
      setHabit(data);
      // The habit analysis has no timezone; the overview does. Failure only
      // means the sleep form falls back to the browser's clock.
      fetchOverviewApi()
        .then((overview) => setTimezone(overview.timezone || ''))
        .catch(() => {});
      setError('');
    } catch (loadError) {
      setError(
        loadError?.status === 404 ? 'Цю звичку не знайдено' : loadError?.message || 'Не вдалося завантажити звичку'
      );
    } finally {
      setIsLoading(false);
    }
  }, [habitId]);

  useEffect(() => {
    setIsLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    if (habit) setStageForm((current) => ({ ...current, stage: habit.stage }));
  }, [habit?.stage]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload and tell the sidebar: its failed-formation highlight depends on the same state.
  const refresh = async () => {
    await load();
    window.dispatchEvent(new Event('habits-changed'));
  };

  const run = async (action, success) => {
    await action();
    notify.success(success);
    await refresh();
  };

  const archive = async () => {
    const accepted = await confirm({
      title: 'Архівувати звичку?',
      message: 'Звичка зникне зі списків культивації. Історію й паспорт збережено, архівацію можна скасувати.',
      confirmLabel: 'Архівувати'
    });
    if (!accepted) return;
    try {
      await archiveHabitApi(habit.id);
      notify.success('Звичку архівовано');
      navigate('/practice');
    } catch (archiveError) {
      notify.error(archiveError?.message || 'Не вдалося архівувати');
    }
  };

  const header = (
    <div className="border-b border-gray-100 bg-white/80 px-4 pb-5 pt-6 backdrop-blur-sm md:px-10 md:pt-10">
      <div className="mx-auto w-full max-w-screen-2xl">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsSidebarOpen(true)}
            className="text-stone-500 hover:text-stone-900 md:hidden"
            aria-label="Відкрити навігацію"
          >
            <Menu size={24} />
          </button>
          <Link to="/practice" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-stone-900">
            <ArrowLeft size={14} /> Культивація
          </Link>
        </div>
        {habit && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-stone-900 md:text-3xl" data-testid="habit-title">
                {habit.name}
              </h1>
              {habit.passport?.description && (
                <p className="mt-1 max-w-2xl text-sm text-stone-600" data-testid="habit-description">
                  {habit.passport.description}
                </p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StageBadge stage={habit.stage} label={habit.stage_label} />
                <LevelBadge ladder={habit.ladder} />
                {(habit.mode || habit.today?.degraded) && <ModeBadge />}
                <span className="text-xs text-gray-400">{KIND_LABELS[habit.kind] || habit.kind}</span>
                {habit.archived && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs text-amber-700">в архіві</span>
                )}
              </div>
            </div>
            {habit.tracker && habit.kind !== 'sleep' && (
              <Link to={`/tracker/${habit.tracker.id}`} className={BUTTON_SECONDARY}>
                Відкрити трекер
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col">
        {header}
        <div className="p-10 text-center text-sm text-gray-500">Завантаження…</div>
      </div>
    );
  }
  if (error || !habit) {
    return (
      <div className="flex flex-1 flex-col">
        {header}
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
          <p className="text-lg font-semibold text-stone-700">{error || 'Цю звичку не знайдено'}</p>
          <Link to="/practice" className={BUTTON_PRIMARY}>
            До культивації
          </Link>
        </div>
      </div>
    );
  }

  const markNeedsReason = mark.status !== 'clear';
  const lastStageChange = habit.stage_changes?.at(-1);
  const attempt = habit.attempt;

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-[#fcfcfc]">
      {header}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10">
        {/* Two columns on wide screens; passport and management keep the full width for their forms. */}
        <div
          className="mx-auto grid w-full max-w-screen-2xl items-start gap-5 xl:grid-cols-2"
          data-testid="habit-content"
        >
          {attempt?.failed_on && !habit.archived && <AttemptDecision habit={habit} onDone={refresh} />}

          <Section title="Сьогодні" testId="today-block">
            <p className="text-sm text-gray-500">
              Ціль: <span className="font-semibold text-stone-900">{habit.today?.requirement || '—'}</span>
            </p>
            {habit.today?.minimum && <p className="text-xs text-gray-500">Мінімум: {habit.today.minimum}</p>}
            {habit.today?.tolerance && (
              <p className="text-xs text-amber-700">Допуск з попередженням: {habit.today.tolerance}</p>
            )}
            {habit.today?.day?.warning && (
              <p className="mt-1 text-xs text-amber-700" data-testid="today-warning">
                {habit.today.day.warning}
              </p>
            )}
            <div className="mt-2">
              <DayStatusPill day={habit.today?.day} />
            </div>
            {habit.today?.day?.detail && <p className="mt-1 text-xs text-gray-500">{habit.today.day.detail}</p>}
            {lastStageChange?.auto && (
              <p className="mt-3 text-xs text-gray-500" data-testid="stage-change">
                Етап «{lastStageChange.to_label}» з {formatDay(lastStageChange.date)} — автоматично.{' '}
                {lastStageChange.reason}
              </p>
            )}
            {habit.recommendation && (
              <p className="mt-3 rounded-xl border border-dashed border-sky-200 bg-sky-50/60 p-3 text-sm text-sky-900">
                <span className="font-semibold">Наступного дня етап зміниться сам:</span> {habit.recommendation.reason}
              </p>
            )}
            {attempt && !attempt.failed_on && attempt.day != null && attempt.days != null && (
              <p className="mt-3 text-xs text-gray-500" data-testid="attempt-day">
                Спроба: день {attempt.day} з {attempt.days}
                {attempt.deadline ? `, до ${formatDay(attempt.deadline)}` : ''}
              </p>
            )}
            {habit.kind === 'sleep' && !habit.archived && (
              <button
                type="button"
                onClick={() => setIsSleepOpen(true)}
                className={`${BUTTON_PRIMARY} mt-3 inline-flex items-center`}
              >
                <Moon size={14} className="mr-1.5" aria-hidden="true" /> Внести сон
              </button>
            )}
          </Section>

          <Section title="Останні 90 днів" testId="calendar-block">
            <Calendar
              days={habit.days}
              kind={habit.kind}
              onPick={(day) => setMark((current) => ({ ...current, date: day.date }))}
            />
          </Section>

          <Section title="Показники" testId="rates-block">
            <Rates rates={habit.rates} />
          </Section>

          <Section title="Критерії інтеграції" testId="integration-block">
            <IntegrationList integration={habit.integration} />
          </Section>

          <Section title="Відновлення" testId="recovery-block">
            <Recovery recovery={habit.recovery} episodes={habit.episodes} />
          </Section>

          {habit.ladder && (
            <Section title="Рівні" testId="ladder-block">
              <LevelsBlock habit={habit} onChanged={refresh} />
            </Section>
          )}

          <Section title="Паспорт" testId="passport-block" className="xl:col-span-2">
            <Passport habit={habit} />
            {!habit.archived && <EditPassport key={habit.versions?.length} habit={habit} onSaved={refresh} />}
            <h3 className="mt-5 text-sm font-semibold text-stone-800">Історія версій</h3>
            <VersionHistory versions={habit.versions} />
          </Section>

          <Section title="Керування" testId="manage-block" className="xl:col-span-2">
            {habit.archived && (
              <p className="mb-4 text-sm text-gray-500">
                Звичка в архіві: щоб вносити дані чи змінювати паспорт, спершу поверніть її.
              </p>
            )}
            <div className="grid gap-6 lg:grid-cols-2">
              {!habit.archived && (
                <>
                  <ActionForm
                    testId="mark-form"
                    title="Позначити день вручну"
                    submitLabel="Зберегти позначку"
                    onSubmit={() =>
                      run(
                        () =>
                          markDayApi(habit.id, {
                            date: mark.date,
                            status: mark.status,
                            ...(markNeedsReason ? { reason: mark.reason.trim() } : {})
                          }),
                        mark.status === 'clear' ? 'Позначку знято' : 'День позначено'
                      )
                    }
                  >
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="Дата">
                        <input
                          type="date"
                          aria-label="Дата позначки"
                          value={mark.date}
                          onChange={(e) => setMark({ ...mark, date: e.target.value })}
                          className={INPUT_CLASS}
                          required
                        />
                      </Field>
                      <Field label="Статус">
                        <select
                          aria-label="Статус позначки"
                          value={mark.status}
                          onChange={(e) => setMark({ ...mark, status: e.target.value })}
                          className={INPUT_CLASS}
                        >
                          <option value="success">Успіх</option>
                          <option value="minimum">Мінімум</option>
                          <option value="fail">Порушення</option>
                          <option value="exception">Виняток</option>
                          <option value="clear">Зняти позначку</option>
                        </select>
                      </Field>
                    </div>
                    {markNeedsReason && (
                      <Field label="Причина">
                        <input
                          type="text"
                          aria-label="Причина позначки"
                          value={mark.reason}
                          onChange={(e) => setMark({ ...mark, reason: e.target.value })}
                          className={INPUT_CLASS}
                          required
                        />
                      </Field>
                    )}
                  </ActionForm>

                  <div className="space-y-3" data-testid="mode-block">
                    <h3 className="text-sm font-semibold text-stone-800">Режим мінімуму</h3>
                    {habit.mode ? (
                      <ActionForm
                        title={`Діє з ${formatDay(habit.mode.start_date)}${habit.mode.reason ? ` — ${habit.mode.reason}` : ''}`}
                        submitLabel="Завершити режим мінімуму"
                        onSubmit={() =>
                          run(
                            () => endModeApi(habit.id, modeReason.trim() ? { reason: modeReason.trim() } : {}),
                            'Режим мінімуму завершено'
                          )
                        }
                      >
                        <input
                          type="text"
                          aria-label="Причина завершення режиму"
                          placeholder="Причина (необов'язково)"
                          value={modeReason}
                          onChange={(e) => setModeReason(e.target.value)}
                          className={INPUT_CLASS}
                        />
                      </ActionForm>
                    ) : (
                      <ActionForm
                        title="Вимогою на час режиму стає мінімум"
                        submitLabel="Увімкнути режим мінімуму"
                        onSubmit={() =>
                          run(
                            () =>
                              startModeApi(habit.id, {
                                reason: modeReason.trim(),
                                ...(modeDate ? { start_date: modeDate } : {})
                              }),
                            'Режим мінімуму увімкнено'
                          )
                        }
                      >
                        <input
                          type="text"
                          aria-label="Причина режиму мінімуму"
                          placeholder="Причина"
                          value={modeReason}
                          onChange={(e) => setModeReason(e.target.value)}
                          className={INPUT_CLASS}
                          required
                        />
                        <input
                          type="date"
                          aria-label="Початок режиму"
                          value={modeDate}
                          onChange={(e) => setModeDate(e.target.value)}
                          className={INPUT_CLASS}
                        />
                      </ActionForm>
                    )}
                  </div>

                  <ActionForm
                    testId="stage-form"
                    title="Змінити етап"
                    submitLabel="Змінити етап"
                    onSubmit={() =>
                      run(
                        () =>
                          changeStageApi(habit.id, {
                            stage: stageForm.stage,
                            reason: stageForm.reason.trim(),
                            ...(stageForm.effective_from ? { effective_from: stageForm.effective_from } : {})
                          }),
                        'Етап змінено'
                      ).then(() => setStageForm((c) => ({ ...c, reason: '' })))
                    }
                  >
                    <p className="text-xs text-gray-500">
                      Етапи змінюються самі, коли виконано критерії. Тут — ручне виправлення; далі критерії діють від
                      нього.
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <select
                        aria-label="Новий етап"
                        value={stageForm.stage}
                        onChange={(e) => setStageForm({ ...stageForm, stage: e.target.value })}
                        className={INPUT_CLASS}
                      >
                        {STAGE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <input
                        type="date"
                        aria-label="Етап діє з"
                        value={stageForm.effective_from}
                        onChange={(e) => setStageForm({ ...stageForm, effective_from: e.target.value })}
                        className={INPUT_CLASS}
                      />
                    </div>
                    <input
                      type="text"
                      aria-label="Причина зміни етапу"
                      placeholder="Причина"
                      value={stageForm.reason}
                      onChange={(e) => setStageForm({ ...stageForm, reason: e.target.value })}
                      className={INPUT_CLASS}
                      required
                    />
                  </ActionForm>
                </>
              )}

              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-stone-800">Архів</h3>
                {habit.archived ? (
                  <button
                    type="button"
                    onClick={() => run(() => unarchiveHabitApi(habit.id), 'Звичку повернено з архіву')}
                    className={BUTTON_SECONDARY}
                  >
                    Повернути з архіву
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={archive}
                    className="rounded-xl border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-600 transition-colors hover:bg-rose-50"
                  >
                    Архівувати звичку
                  </button>
                )}
              </div>
            </div>
          </Section>
        </div>
      </div>

      {isSleepOpen && (
        <SleepEntryModal habit={habit} timezone={timezone} onClose={() => setIsSleepOpen(false)} onSaved={refresh} />
      )}
    </div>
  );
}

export default HabitDetailPage;
