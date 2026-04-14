import React, { useEffect, useState } from 'react';
import { apiFetch } from '../http';
import { useAdmin } from '../context/AdminContext';

export default function AdminStatus() {
  const { admin } = useAdmin();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch('admin/status')
      .then((data) => setStatus(data))
      .catch(() => setError('Failed to load system status'));
  }, []);

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div style={{ padding: 32, color: 'red' }}>
        Access denied: Only admin or superadmin can view system status.
      </div>
    );
  }

  return (
    <div style={{ padding: 32 }}>
      <h3>System Status</h3>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {status && (
        <div style={{ textAlign: 'left', display: 'inline-block' }} aria-label='System status summary'>
          <div title='Total users'>
            <b>Users:</b> {status.users.total} (active: {status.users.active})
          </div>
          <div title='Total polls'>
            <b>Polls:</b> {status.polls.total} (archived: {status.polls.archived})
          </div>
          <div title='Audit logs in last 24 hours'>
            <b>Audit logs (last 24h):</b> {status.auditLogs.last24h}
          </div>
          <div title='Status timestamp'>
            <b>Timestamp:</b> {status.timestamp}
          </div>
        </div>
      )}
    </div>
  );
}
