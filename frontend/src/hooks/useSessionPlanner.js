import { useState, useCallback } from 'react';
import {
  buildBulkSessionPayload,
  validateSessionSchedule,
  checkAvailabilityForSlots,
} from '@/lib/sessionScheduling';

/**
 * Ortak seans planlama state — Wizard + SessionsHub ile aynı mantık.
 */
export function useSessionPlanner(api) {
  const [sessionRows, setSessionRows] = useState([]);
  const [checking, setChecking] = useState(false);

  const runBulkCheck = useCallback(
    async ({ service_id, staff_id, slots, staff_ids }) => {
      setChecking(true);
      try {
        return await checkAvailabilityForSlots(api, {
          service_id,
          staff_id,
          slots,
          staff_ids,
        });
      } finally {
        setChecking(false);
      }
    },
    [api]
  );

  const validate = useCallback((sessions) => validateSessionSchedule(sessions), []);

  const buildPayload = useCallback((fields) => buildBulkSessionPayload(fields), []);

  return {
    sessionRows,
    setSessionRows,
    checking,
    runBulkCheck,
    validate,
    buildPayload,
  };
}
