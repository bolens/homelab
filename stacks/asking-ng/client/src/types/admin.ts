/** Admin JWT / `admin/me` payload (subset used by the UI). */
export type AdminRole = 'admin' | 'superadmin' | 'mod' | 'user';

export interface AdminUser {
  id: number;
  homelab-user: string;
  role: AdminRole;
}
