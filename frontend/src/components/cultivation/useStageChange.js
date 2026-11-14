import { useState } from 'react';
import { useAppState } from '../../state/appState';
import { STAGE_OPTIONS } from './helpers';

const stageLabel = (stage) => STAGE_OPTIONS.find((option) => option.value === stage)?.label || stage;

/**
 * Apply a stage change: shared by the recommendation button and the manual
 * stage form. Never called automatically — it always needs a typed reason.
 */
export function useStageChange(onChanged) {
  const { confirm, notify } = useAppState();
  const [pending, setPending] = useState(null);

  /** Recommendation flow: ConfirmDialog first, then the reason prompt. */
  const proposeRecommendation = async (habit) => {
    const rec = habit.recommendation;
    if (!rec) return;
    const accepted = await confirm({
      title: `Змінити етап на «${stageLabel(rec.to)}»?`,
      message: rec.reason,
      confirmLabel: 'Далі',
      tone: 'neutral'
    });
    if (accepted) setPending({ habit, stage: rec.to, suggestedReason: rec.reason });
  };

  return {
    pending,
    setPending,
    proposeRecommendation,
    notifyChanged: () => {
      setPending(null);
      notify.success('Етап змінено');
      onChanged?.();
    }
  };
}
