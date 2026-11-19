import { useEffect, useState } from 'react';
import { fetchHabitsApi } from '../services/cultivationApi';

/** The cultivated habit a tracker feeds, or null for a plain tracker. */
export function useTrackerHabit(trackerId) {
  const [habit, setHabit] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setHabit(null);
    if (!trackerId) return undefined;
    fetchHabitsApi()
      .then((habits) => {
        if (!cancelled) setHabit(habits.find((item) => item.tracker?.id === trackerId) || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [trackerId]);

  return habit;
}
