import React, { useState } from 'react';
import { useAdmin } from '../context/AdminContext';

const apiRoot = () => (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

async function downloadExport(path, filename) {
  const token = localStorage.getItem('adminToken');
  const url = `${apiRoot()}${path}`;
  const res = await fetch(url, { headers: token ? { 'x-admin-token': token } : {} });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }, 100);
}

export default function AdminExport() {
  const { admin } = useAdmin();
  const [error, setError] = useState('');

  const run = async (path, filename) => {
    setError('');
    try {
      await downloadExport(path, filename);
    } catch {
      setError('Download failed (check admin token and API path).');
    }
  };

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div style={{ padding: 32, color: 'red' }}>Access denied: Only admin or superadmin can export data.</div>
    );
  }

  const base = '/admin/export';
  return (
    <div style={{ padding: 32 }}>
      <h3>Export Data</h3>
      {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
      <ul style={{ listStyle: 'none', padding: 0 }}>
        <li>
          <button type='button' onClick={() => run(`${base}/users?format=json`, 'users.json')}>
            Export Users (JSON)
          </button>
        </li>
        <li>
          <button type='button' onClick={() => run(`${base}/users?format=csv`, 'users.csv')}>
            Export Users (CSV)
          </button>
        </li>
        <li>
          <button type='button' onClick={() => run(`${base}/polls?format=json`, 'polls.json')}>
            Export Polls (JSON)
          </button>
        </li>
        <li>
          <button type='button' onClick={() => run(`${base}/polls?format=csv`, 'polls.csv')}>
            Export Polls (CSV)
          </button>
        </li>
        <li>
          <button type='button' onClick={() => run(`${base}/audit-logs?format=json`, 'audit_logs.json')}>
            Export Audit Logs (JSON)
          </button>
        </li>
        <li>
          <button type='button' onClick={() => run(`${base}/audit-logs?format=csv`, 'audit_logs.csv')}>
            Export Audit Logs (CSV)
          </button>
        </li>
      </ul>
    </div>
  );
}
