import { useState } from 'react';
import { changeStageApi } from '../../services/cultivationApi';
import Modal from '../ui/Modal';
import { Field } from './common';
import { BUTTON_PRIMARY, BUTTON_SECONDARY, INPUT_CLASS, STAGE_OPTIONS } from './helpers';

const stageLabel = (stage) => STAGE_OPTIONS.find((option) => option.value === stage)?.label || stage;

function StageReasonModal({ pending, onClose, onDone }) {
  const [reason, setReason] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  if (!pending) return null;

  const submit = async (event) => {
    event.preventDefault();
    if (!reason.trim()) {
      setError('Вкажіть причину зміни етапу');
      return;
    }
    setIsSaving(true);
    try {
      await changeStageApi(pending.habit.id, { stage: pending.stage, reason: reason.trim() });
      setReason('');
      onDone();
    } catch (saveError) {
      setError(saveError?.message || 'Не вдалося змінити етап');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} size="md" title={`Етап: ${stageLabel(pending.stage)}`} description={pending.habit.name}>
      <form onSubmit={submit} className="space-y-4">
        {pending.suggestedReason && <p className="text-sm text-gray-500">Підстава рекомендації: {pending.suggestedReason}</p>}
        <Field label="Причина зміни">
          <input type="text" aria-label="Причина зміни етапу" value={reason} onChange={(event) => setReason(event.target.value)} className={INPUT_CLASS} />
        </Field>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={BUTTON_SECONDARY}>Скасувати</button>
          <button type="submit" disabled={isSaving} className={BUTTON_PRIMARY}>{isSaving ? 'Збереження…' : 'Застосувати'}</button>
        </div>
      </form>
    </Modal>
  );
}

export default StageReasonModal;
