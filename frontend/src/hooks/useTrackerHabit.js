import { useEffect, useState } from 'react';
import { fetchHabitsApi } from '../services/cultivationApi';

/** The cultivated habit a tracker feeds, or null for a plain tracker. */
export function useTrackerHabit(trackerId) {
  const [habit, setHabit] = useState(null);
  const [version, setVersion] = useState(0);

  // Pausing or resuming a tracker changes its habit as well.
  useEffect(() => {
    const onChanged = () => setVersion((value) => value + 1);
    window.addEventListener('habits-changed', onChanged);
    return () => window.removeEventListener('habits-changed', onChanged);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!trackerId) {
      setHabit(null);
      return undefined;
    }
    fetchHabitsApi()
      .then((habits) => {
        if (!cancelled) setHabit(habits.find((item) => item.tracker?.id === trackerId) || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [trackerId, version]);

  useEffect(() => {
    setHabit(null);
  }, [trackerId]);

  return habit;
}
