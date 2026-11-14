import { useState } from 'react';
import { createHabitApi } from '../../services/cultivationApi';
import { useAppState } from '../../state/appState';
import Modal from '../ui/Modal';
import LevelFields from './LevelFields';
import { buildLevel, emptyLevel, hasLevelValue } from './levelHelpers';
import { Field } from './common';
import { BUTTON_PRIMARY, BUTTON_SECONDARY, INPUT_CLASS, KIND_OPTIONS, STAGE_OPTIONS } from './helpers';

const initialState = () => ({
  kind: 'sleep',
  name: '',
  stage: 'formation',
  level: emptyLevel(),
  withMinimum: false,
  minimum: emptyLevel(),
  unit: '',
  priority: '',
  reason: ''
});

function NewHabitModal({ isOpen, onClose, onCreated }) {
  const { notify } = useAppState();
  const [form, setForm] = useState(initialState);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const close = () => {
    setForm(initialState());
    setError('');
    onClose();
  };

  const submit = async (event) => {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setError('Вкажіть назву звички');
      return;
    }
    if (form.kind === 'sleep' && !hasLevelValue('sleep', form.level)) {
      setError('Для сну вкажіть хоча б один поріг: підйом, мінімум або максимум годин');
      return;
    }

    const spec = { name, stage: form.stage, level: buildLevel(form.kind, form.level) };
    if (form.kind === 'build') spec.unit = form.unit.trim();
    if (form.withMinimum && hasLevelValue(form.kind, form.minimum)) {
      spec.minimum = buildLevel(form.kind, form.minimum);
    }
    if (form.priority !== '') spec.priority = Number(form.priority);

    const payload = { kind: form.kind, spec };
    if (form.reason.trim()) payload.reason = form.reason.trim();

    setIsSaving(true);
    setError('');
    try {
      const created = await createHabitApi(payload);
      notify.success('Звичку додано до культивації');
      setForm(initialState());
      onCreated?.(created);
      onClose();
    } catch (saveError) {
      setError(saveError?.message || 'Не вдалося створити звичку');
    } finally {
      setIsSaving(false);
    }
  };

  const canHaveMinimum = form.kind === 'sleep' || form.kind === 'build';

  return (
    <Modal
      isOpen
      onClose={close}
      size="xl"
      title="Нова звичка для культивації"
      description="Паспорт можна буде змінити пізніше; історія версій зберігається."
    >
      <form onSubmit={submit} className="space-y-4" id="new-habit-form">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Тип">
            <select aria-label="Тип" value={form.kind} onChange={set('kind')} className={INPUT_CLASS}>
              {KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Етап">
            <select aria-label="Етап" value={form.stage} onChange={set('stage')} className={INPUT_CLASS}>
              {STAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Назва">
          <input
            type="text"
            aria-label="Назва"
            value={form.name}
            onChange={set('name')}
            className={INPUT_CLASS}
            required
          />
        </Field>

        <fieldset className="space-y-3">
          <legend className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">Вимога</legend>
          <LevelFields kind={form.kind} value={form.level} onChange={(level) => setForm((c) => ({ ...c, level }))} />
          {form.kind === 'build' && (
            <Field label="Одиниця виміру">
              <input
                type="text"
                aria-label="Одиниця виміру"
                value={form.unit}
                onChange={set('unit')}
                className={INPUT_CLASS}
                placeholder="сторінок"
              />
            </Field>
          )}
        </fieldset>

        {canHaveMinimum && (
          <fieldset className="space-y-3">
            <label className="flex items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                checked={form.withMinimum}
                onChange={(event) => setForm((c) => ({ ...c, withMinimum: event.target.checked }))}
              />
              Додати мінімум (полегшена вимога для режиму мінімуму)
            </label>
            {form.withMinimum && (
              <LevelFields
                kind={form.kind}
                prefix="Мінімум: "
                value={form.minimum}
                onChange={(minimum) => setForm((c) => ({ ...c, minimum }))}
              />
            )}
          </fieldset>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Пріоритет" hint="Менше число — вище в списку">
            <input
              type="number"
              min="0"
              step="1"
              aria-label="Пріоритет"
              value={form.priority}
              onChange={set('priority')}
              className={INPUT_CLASS}
            />
          </Field>
          <Field label="Причина / нотатка до першої версії">
            <input
              type="text"
              aria-label="Причина"
              value={form.reason}
              onChange={set('reason')}
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
          <button type="button" onClick={close} className={BUTTON_SECONDARY}>
            Скасувати
          </button>
          <button type="submit" disabled={isSaving} className={BUTTON_PRIMARY}>
            {isSaving ? 'Збереження…' : 'Створити'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default NewHabitModal;
