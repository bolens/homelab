import React, { useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../http';

export default function AdminLogin() {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setAdmin } = useAdmin();

  const handleLogin = async e => {
    e.preventDefault();
    if (!token) return setError('Admin token required');
    try {
      // Fetch current admin info (id, homelab-user, role)
      const data = await apiFetch('admin/me', { adminToken: token });
      localStorage.setItem('adminToken', token);
      setAdmin(data.admin); // { id, homelab-user, role }
      setError('');
      navigate('/admin');
    } catch {
      setError('Invalid admin token');
    }
  };

  return (
    <div style={{ padding: 32 }}>
      <h2>Admin Login</h2>
      <form onSubmit={handleLogin} aria-label="Admin login form">
        <input
          type='password'
          placeholder='Admin Token'
          value={token}
          onChange={e => setToken(e.target.value)}
          style={{ width: 240, marginBottom: 8 }}
          aria-label="Admin token"
          required
        />
        <br />
        <button type='submit' aria-label="Login as admin" title="Login as admin">Login</button>
      </form>
      {error && <div style={{ color: 'red', marginTop: 8 }}>{error}</div>}
    </div>
  );
}
