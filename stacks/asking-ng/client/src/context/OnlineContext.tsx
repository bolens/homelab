import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

type OnlineContextValue = { online: boolean };

const OnlineContext = createContext<OnlineContextValue>({ online: true });

export function OnlineProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  );

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  const value = useMemo(() => ({ online }), [online]);
  return <OnlineContext.Provider value={value}>{children}</OnlineContext.Provider>;
}

export function useOnline(): boolean {
  return useContext(OnlineContext).online;
}
