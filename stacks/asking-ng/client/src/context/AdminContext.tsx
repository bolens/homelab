import React, {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { apiFetch } from '../http';
import { getStoredUserJwt, subscribeUserJwtChanged } from '../lib/userSession';
import type { AdminUser } from '../types/admin';

type AdminMeResponse = { admin: AdminUser };

interface AdminContextValue {
  admin: AdminUser | null;
  setAdmin: (user: AdminUser | null) => void;
  /** False only until the first admin session bootstrap (`admin/me`) finishes. */
  adminSessionReady: boolean;
}

const AdminContext = createContext<AdminContextValue | null>(null);

export function AdminProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [adminSessionReady, setAdminSessionReady] = useState(false);
  const initialHydrationDone = useRef(false);

  const finishInitialHydration = useCallback(() => {
    if (!initialHydrationDone.current) {
      initialHydrationDone.current = true;
      setAdminSessionReady(true);
    }
  }, []);

  const bootstrapFromStorage = useCallback(async () => {
    const token = localStorage.getItem('adminToken');
    const sessionJwt = getStoredUserJwt();
    if (!token?.trim() && !sessionJwt?.trim()) {
      setAdmin(null);
      finishInitialHydration();
      return;
    }
    try {
      const data = (await apiFetch('admin/me')) as AdminMeResponse;
      setAdmin(data.admin);
    } catch {
      const hadAdminToken = Boolean(localStorage.getItem('adminToken')?.trim());
      if (hadAdminToken) {
        try {
          localStorage.removeItem('adminToken');
        } catch {
          /* private mode */
        }
      }
      setAdmin(null);
    } finally {
      finishInitialHydration();
    }
  }, [finishInitialHydration]);

  useEffect(() => {
    void bootstrapFromStorage();
  }, [bootstrapFromStorage]);

  useEffect(() => {
    return subscribeUserJwtChanged(() => {
      void bootstrapFromStorage();
    });
  }, [bootstrapFromStorage]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== 'adminToken') return;
      if (!e.newValue) setAdmin(null);
      else void bootstrapFromStorage();
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [bootstrapFromStorage]);

  return (
    <AdminContext.Provider value={{ admin, setAdmin, adminSessionReady }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin(): AdminContextValue {
  const ctx = useContext(AdminContext);
  if (!ctx) {
    throw new Error('useAdmin must be used within AdminProvider');
  }
  return ctx;
}
