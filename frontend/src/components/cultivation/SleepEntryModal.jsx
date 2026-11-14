import { useEffect, useState } from 'react';
import { logSleepApi } from '../../services/cultivationApi';
import { useAppState } from '../../state/appState';
import Modal from '../ui/Modal';
import { Field } from './common';
import { BUTTON_PRIMARY, BUTTON_SECONDARY, INPUT_CLASS, defaultSleepTimes } from './helpers';

/**
 * Quick sleep entry. The datetime-local values are naive local times and are
 * sent as-is: the backend interprets them in the user's timezone, so they must
 * never go through toISOString() (that would shift them to UTC).
 */
function SleepEntryModal({ habit, timezone, onClose, onSaved }) {
  const { notify } = useAppState();
  const [form, setForm] = useState(() => ({ ...defaultSleepTimes(timezone), reason: '', state: '', note: '' }));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (habit) {
      setForm({ ...defaultSleepTimes(timezone), reason: '', state: '', note: '' });
      setError('');
    }
  }, [habit, timezone]);

  if (!habit) return null;

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.bedtime || !form.wake) {
      setError('Вкажіть час засинання та пробудження');
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      const payload = { bedtime: form.bedtime, wake: form.wake };
      if (form.reason.trim()) payload.reason = form.reason.trim();
      if (form.state.trim()) payload.state = form.state.trim();
      if (form.note.trim()) payload.note = form.note.trim();
      const result = await logSleepApi(habit.id, payload);
      const hours = Number.isFinite(Number(result.hours)) ? ` (${Number(result.hours).toLocaleString('uk-UA', { maximumFractionDigits: 1 })} год)` : '';
      notify.success(`Сон записано${hours}: ${result.day?.status_label || 'без оцінки'}`);
      onSaved?.(result);
      onClose();
    } catch (saveError) {
      setError(saveError?.message || 'Не вдалося записати сон');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} size="md" title="Внести сон" description={habit.name}>
      <form onSubmit={submit} className="space-y-4" id="sleep-entry-form">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Заснув(ла)">
            <input type="datetime-local" aria-label="Час засинання" value={form.bedtime} onChange={update('bedtime')} className={INPUT_CLASS} required />
          </Field>
          <Field label="Прокинувся(лась)">
            <input type="datetime-local" aria-label="Час пробудження" value={form.wake} onChange={update('wake')} className={INPUT_CLASS} required />
          </Field>
        </div>
        <Field label="Причина відхилення" hint="Необов'язково">
          <input type="text" aria-label="Причина відхилення" value={form.reason} onChange={update('reason')} className={INPUT_CLASS} />
        </Field>
        <Field label="Стан наступного дня" hint="Необов'язково, кілька слів">
          <input type="text" aria-label="Стан наступного дня" value={form.state} onChange={update('state')} className={INPUT_CLASS} maxLength={120} />
        </Field>
        <Field label="Нотатка">
          <textarea aria-label="Нотатка" value={form.note} onChange={update('note')} rows={2} className={INPUT_CLASS} />
        </Field>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={BUTTON_SECONDARY}>Скасувати</button>
          <button type="submit" disabled={isSaving} className={BUTTON_PRIMARY}>
            {isSaving ? 'Збереження…' : 'Записати сон'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default SleepEntryModal;
