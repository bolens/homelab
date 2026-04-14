import React, { useState } from 'react';
import { apiFetch } from '../http';
import { useAdmin } from '../context/AdminContext';

export default function AdminImpersonate() {
  const { admin } = useAdmin();
  const [userId, setUserId] = useState('');
  const [token, setToken] = useState('');
  const [error, setError] = useState('');

  const handleImpersonate = async (e) => {
    e.preventDefault();
    setError('');
    setToken('');
    if (!userId) return setError('User ID required');
    try {
      const data = await apiFetch(`admin/impersonate/${userId}`, { method: 'POST', body: {} });
      setToken(data.token);
    } catch {
      setError('Failed to impersonate user');
    }
  };

  if (!admin || admin.role !== 'superadmin') {
    return (
      <div style={{ padding: 32, color: 'red' }}>Access denied: Only superadmin can impersonate users.</div>
    );
  }

  return (
    <div style={{ padding: 32 }}>
      <h3>Impersonate User</h3>
      <form onSubmit={handleImpersonate} aria-label='Impersonate user form'>
        <input
          type='number'
          placeholder='User ID'
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          style={{ width: 120, marginRight: 8 }}
          aria-label='User ID to impersonate'
          required
        />
        <button type='submit' aria-label='Impersonate user' title='Impersonate user'>
          Impersonate
        </button>
      </form>
      {token && (
        <div style={{ marginTop: 16 }}>
          <b>JWT:</b>
          <textarea value={token} readOnly style={{ width: 320, height: 60, marginTop: 8 }} aria-label='Impersonation JWT token' />
        </div>
      )}
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
    </div>
  );
}
