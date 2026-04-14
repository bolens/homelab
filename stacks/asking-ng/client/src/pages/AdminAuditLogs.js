import React, { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../http';
import { useAdmin } from '../context/AdminContext';

export default function AdminAuditLogs() {
  const { admin } = useAdmin();
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');
  const [action, setAction] = useState('');
  const [actor, setActor] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');

  const fetchLogs = useCallback(() => {
    let url = 'admin/audit-logs?';
    if (action) url += `action=${encodeURIComponent(action)}&`;
    if (actor) url += `actor=${encodeURIComponent(actor)}&`;
    if (start) url += `start=${encodeURIComponent(start)}&`;
    if (end) url += `end=${encodeURIComponent(end)}&`;
    apiFetch(url)
      .then((data) => setLogs(data.logs))
      .catch(() => setError('Failed to load audit logs'));
  }, [action, actor, start, end]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div style={{ padding: 32, color: 'red' }}>
        Access denied: Only admin or superadmin can view audit logs.
      </div>
    );
  }

  return (
    <div style={{ padding: 32 }}>
      <h3>Audit Logs</h3>
      <div style={{ marginBottom: 16 }}>
        <input
          placeholder='Action'
          value={action}
          onChange={(e) => setAction(e.target.value)}
          style={{ marginRight: 8 }}
          aria-label='Filter by action'
        />
        <input
          placeholder='Actor'
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          style={{ marginRight: 8 }}
          aria-label='Filter by actor'
        />
        <input
          type='date'
          value={start}
          onChange={(e) => setStart(e.target.value)}
          style={{ marginRight: 8 }}
          aria-label='Start date'
        />
        <input
          type='date'
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          style={{ marginRight: 8 }}
          aria-label='End date'
        />
        <button type='button' onClick={fetchLogs} aria-label='Apply filters' title='Apply filters'>
          Filter
        </button>
      </div>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      <table style={{ margin: '0 auto' }}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Action</th>
            <th>Actor</th>
            <th>Target</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id}>
              <td>{l.id}</td>
              <td>{l.action}</td>
              <td>{l.actor}</td>
              <td>{l.target}</td>
              <td>{l.createdAt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
