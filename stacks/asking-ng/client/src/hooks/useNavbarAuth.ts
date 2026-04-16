import { useEffect, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { apiFetch } from '../http';
import { hasAdminRouteCredential } from '../lib/jwtRole';
import { getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';

/**
 * JWT presence and admin-route gate for the main navbar (mirrors prior inline effects).
 */
export function useNavbarAuth() {
  const [userJwtPresent, setUserJwtPresent] = useState(() => Boolean(getStoredUserJwt()));
  const { admin, adminSessionReady } = useAdmin();
  const [adminGateCredential, setAdminGateCredential] = useState(() => hasAdminRouteCredential());
  const [noAdminExists, setNoAdminExists] = useState(false);

  useEffect(() => {
    const syncUser = () => setUserJwtPresent(Boolean(getStoredUserJwt()));
    syncUser();
    return subscribeUserJwtChanged(syncUser);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const data = (await apiFetch('admin/bootstrap-status', {
          adminToken: false,
        })) as { noAdminExists?: unknown };
        setNoAdminExists(data.noAdminExists === true);
      } catch {
        setNoAdminExists(false);
      }
    })();
  }, []);

  useEffect(() => {
    const syncAdminGate = () => setAdminGateCredential(hasAdminRouteCredential());
    syncAdminGate();
    const onStorage = (e: StorageEvent) => {
      if (e.key !== 'adminToken') return;
      syncAdminGate();
    };
    window.addEventListener('storage', onStorage);
    const unsubJwt = subscribeUserJwtChanged(syncAdminGate);
    return () => {
      window.removeEventListener('storage', onStorage);
      unsubJwt();
    };
  }, [admin]);

  return { userJwtPresent, admin, adminSessionReady, adminGateCredential, noAdminExists };
}
