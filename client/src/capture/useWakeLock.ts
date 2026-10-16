/**
 * Screen Wake Lock hook — keeps mobile display awake while shopkeeper works.
 * Docs: docs/03-build-plan.md Phase 7.
 */

import { useEffect, useRef } from 'react';

export function useWakeLock(enabled: boolean = true) {
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled || typeof navigator === 'undefined' || !('wakeLock' in navigator)) {
      return;
    }

    let isMounted = true;

    async function requestWakeLock() {
      try {
        wakeLockRef.current = await navigator.wakeLock.request('screen');
      } catch {
        // WakeLock request can fail if battery is low or page is backgrounded
      }
    }

    requestWakeLock();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isMounted) {
        requestWakeLock();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMounted = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (wakeLockRef.current) {
        wakeLockRef.current.release().catch(() => {});
        wakeLockRef.current = null;
      }
    };
  }, [enabled]);
}

