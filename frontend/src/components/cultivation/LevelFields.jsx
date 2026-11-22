import { Field } from './common';
import { INPUT_CLASS } from './helpers';

/** Level inputs for one kind; `prefix` keeps aria-labels unique per block. */
function LevelFields({ kind, value, onChange, prefix = '' }) {
  const set = (key) => (event) => onChange({ ...value, [key]: event.target.value });
  const label = (text) => `${prefix}${text}`;

  if (kind === 'sleep') {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Підйом не пізніше">
          <input
            type="time"
            aria-label={label('Підйом не пізніше')}
            value={value.wake_by}
            onChange={set('wake_by')}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label="Заснути до" hint="Порожньо — час засинання не оцінюється.">
          <input
            type="time"
            aria-label={label('Заснути до')}
            value={value.bed_by}
            onChange={set('bed_by')}
            className={INPUT_CLASS}
          />
        </Field>
        <Field label="Сон від, год">
          <input
            type="number"
            step="0.25"
            min="0"
            max="24"
            aria-label={label('Сон від, год')}
            value={value.min_sleep_h}
            onChange={set('min_sleep_h')}
            className={INPUT_CLASS}
            placeholder="7"
          />
        </Field>
        <Field label="Сон до, год">
          <input
            type="number"
            step="0.25"
            min="0"
            max="24"
            aria-label={label('Сон до, год')}
            value={value.max_sleep_h}
            onChange={set('max_sleep_h')}
            className={INPUT_CLASS}
            placeholder="9"
          />
        </Field>
      </div>
    );
  }
  if (kind === 'build') {
    return (
      <Field label="Мінімальна кількість">
        <input
          type="number"
          step="any"
          min="0"
          aria-label={label('Мінімальна кількість')}
          value={value.min_amount}
          onChange={set('min_amount')}
          className={INPUT_CLASS}
        />
      </Field>
    );
  }
  if (kind === 'boolean') {
    return (
      <Field label="Виконати до" hint="Порожньо — підходить будь-який час дня.">
        <input
          type="time"
          aria-label={label('Виконати до')}
          value={value.done_by}
          onChange={set('done_by')}
          className={INPUT_CLASS}
        />
      </Field>
    );
  }
  return <p className="text-sm text-gray-500">Для цього типу додаткових порогів не потрібно.</p>;
}

export default LevelFields;
