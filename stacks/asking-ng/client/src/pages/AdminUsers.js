import React, { useEffect, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useAdminWebSocket } from '../wsClient';
import { apiFetch } from '../http';

export default function AdminUsers() {
  const { admin } = useAdmin();
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [sortBy, setSortBy] = useState('id');
  const [sortDir, setSortDir] = useState('asc');
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [newUser, setNewUser] = useState({ homelab-user: '', password: '', role: 'user' });
  const [resetPw, setResetPw] = useState({ id: '', password: '' });
  const [roleEdit, setRoleEdit] = useState({ id: '', role: 'user' });

  useAdminWebSocket({
    onUserUpdate: (userList) => setUsers(userList),
  });

  useEffect(() => {
    apiFetch('admin/users')
      .then((data) => setUsers(data.users))
      .catch(() => setError('Failed to load users'));
  }, [refresh]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError('');
    if (!newUser.homelab-user || !newUser.password) return setError('Username and password required');
    try {
      await apiFetch('admin/users', { method: 'POST', body: newUser });
      setNewUser({ homelab-user: '', password: '', role: 'user' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to create user');
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');
    if (!resetPw.id || !resetPw.password) return setError('User ID and new password required');
    try {
      await apiFetch(`admin/users/${resetPw.id}/reset-password`, {
        method: 'POST',
        body: { password: resetPw.password },
      });
      setResetPw({ id: '', password: '' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to reset password');
    }
  };

  const handleChangeRole = async (e) => {
    e.preventDefault();
    setError('');
    if (!roleEdit.id) return setError('User ID required');
    try {
      await apiFetch(`admin/users/${roleEdit.id}/role`, {
        method: 'PATCH',
        body: { role: roleEdit.role },
      });
      setRoleEdit({ id: '', role: 'user' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to change role');
    }
  };

  const handleDeleteUser = async (id) => {
    if (!window.confirm(`Delete user ${id}?`)) return;
    setError('');
    try {
      await apiFetch(`admin/users/${id}`, { method: 'DELETE' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to delete user');
    }
  };

  const handleSelect = (id) => {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  };

  const handleBulk = async (action) => {
    setError('');
    for (const id of selected) {
      try {
        if (action === 'suspend') {
          await apiFetch(`admin/users/${id}/suspend`, { method: 'PATCH', body: {} });
        }
        if (action === 'activate') {
          await apiFetch(`admin/users/${id}/activate`, { method: 'PATCH', body: {} });
        }
        if (action === 'delete') {
          await apiFetch(`admin/users/${id}`, { method: 'DELETE' });
        }
      } catch {
        setError(`Bulk action failed on user ${id}`);
      }
    }
    setSelected([]);
    setRefresh((r) => r + 1);
  };

  const handleSuspend = async (id) => {
    try {
      await apiFetch(`admin/users/${id}/suspend`, { method: 'PATCH', body: {} });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to suspend user');
    }
  };

  const handleActivate = async (id) => {
    try {
      await apiFetch(`admin/users/${id}/activate`, { method: 'PATCH', body: {} });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to activate user');
    }
  };

  let filteredUsers = users.filter(
    (u) =>
      (u.homelab-user.toLowerCase().includes(search.toLowerCase()) || String(u.id) === search) &&
      (roleFilter ? u.role === roleFilter : true) &&
      (activeFilter ? (activeFilter === 'active' ? u.active : !u.active) : true)
  );

  filteredUsers = filteredUsers.sort((a, b) => {
    let v1 = a[sortBy];
    let v2 = b[sortBy];
    if (typeof v1 === 'string') v1 = v1.toLowerCase();
    if (typeof v2 === 'string') v2 = v2.toLowerCase();
    if (v1 < v2) return sortDir === 'asc' ? -1 : 1;
    if (v1 > v2) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return <div style={{ padding: 32, color: 'red' }}>Access denied: Only admin or superadmin can manage users.</div>;
  }

  return (
    <div className='admin-users-container' style={{ padding: 32 }}>
      <h3>Users</h3>
      {error && <div className='admin-users-error'>{error}</div>}

      <div className='admin-users-search-bar' style={{ marginBottom: 12 }}>
        <input
          placeholder='Search by homelab-user or ID'
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className='admin-users-input'
        />
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className='admin-users-input-short'>
          <option value=''>All Roles</option>
          <option value='user'>User</option>
          <option value='admin'>Admin</option>
          <option value='superadmin'>Superadmin</option>
        </select>
        <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className='admin-users-input-short'>
          <option value=''>All Status</option>
          <option value='active'>Active</option>
          <option value='inactive'>Inactive</option>
        </select>
        <button
          type='button'
          onClick={() => {
            setSearch('');
            setRoleFilter('');
            setActiveFilter('');
            setRefresh((r) => r + 1);
          }}
        >
          Clear
        </button>
      </div>

      {admin.role === 'superadmin' && (
        <form onSubmit={handleChangeRole} className='admin-users-form' style={{ marginBottom: 12 }}>
          <b>Change Role:</b>
          <input
            placeholder='User ID'
            value={roleEdit.id}
            onChange={(e) => setRoleEdit({ ...roleEdit, id: e.target.value })}
            className='admin-users-input-short'
          />
          <select value={roleEdit.role} onChange={(e) => setRoleEdit({ ...roleEdit, role: e.target.value })} className='admin-users-input'>
            <option value='user'>user</option>
            <option value='admin'>admin</option>
            <option value='superadmin'>superadmin</option>
          </select>
          <button type='submit' className='admin-users-btn'>
            Change
          </button>
        </form>
      )}

      <div className='admin-users-bulk-actions' style={{ marginBottom: 12 }}>
        <b>Bulk Actions:</b>
        <button type='button' onClick={() => handleBulk('suspend')} disabled={selected.length === 0} className='admin-users-btn'>
          Suspend
        </button>
        <button type='button' onClick={() => handleBulk('activate')} disabled={selected.length === 0} className='admin-users-btn'>
          Activate
        </button>
        <button type='button' onClick={() => handleBulk('delete')} disabled={selected.length === 0} className='admin-users-btn admin-users-btn-delete'>
          Delete
        </button>
        <span className='admin-users-bulk-selected'>{selected.length} selected</span>
      </div>

      <form onSubmit={handleCreateUser} className='admin-users-form' style={{ marginBottom: 12 }}>
        <b>Create User:</b>
        <input
          placeholder='Username'
          value={newUser.homelab-user}
          onChange={(e) => setNewUser({ ...newUser, homelab-user: e.target.value })}
          className='admin-users-input'
        />
        <input
          type='password'
          placeholder='Password'
          value={newUser.password}
          onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
          className='admin-users-input'
        />
        <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className='admin-users-input'>
          <option value='user'>user</option>
          <option value='admin'>admin</option>
          {admin.role === 'superadmin' && <option value='superadmin'>superadmin</option>}
        </select>
        <button type='submit' className='admin-users-btn'>
          Create
        </button>
      </form>

      <form onSubmit={handleResetPassword} className='admin-users-form' style={{ marginBottom: 12 }}>
        <b>Reset Password:</b>
        <input
          placeholder='User ID'
          value={resetPw.id}
          onChange={(e) => setResetPw({ ...resetPw, id: e.target.value })}
          className='admin-users-input-short'
        />
        <input
          type='password'
          placeholder='New Password'
          value={resetPw.password}
          onChange={(e) => setResetPw({ ...resetPw, password: e.target.value })}
          className='admin-users-input'
        />
        <button type='submit' className='admin-users-btn'>
          Reset
        </button>
      </form>

      <table className='admin-users-table'>
        <thead>
          <tr>
            <th onClick={() => setSortBy('id')}>ID {sortBy === 'id' ? (sortDir === 'asc' ? '▲' : '▼') : ''}</th>
            <th onClick={() => setSortBy('homelab-user')}>Username {sortBy === 'homelab-user' ? (sortDir === 'asc' ? '▲' : '▼') : ''}</th>
            <th onClick={() => setSortBy('role')}>Role {sortBy === 'role' ? (sortDir === 'asc' ? '▲' : '▼') : ''}</th>
            <th onClick={() => setSortBy('active')}>Active {sortBy === 'active' ? (sortDir === 'asc' ? '▲' : '▼') : ''}</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredUsers.map((u) => (
            <tr key={u.id}>
              <td>
                <input type='checkbox' checked={selected.includes(u.id)} onChange={() => handleSelect(u.id)} /> {u.id}
              </td>
              <td>{u.homelab-user}</td>
              <td>{u.role}</td>
              <td>{u.active ? 'Yes' : 'No'}</td>
              <td>
                {u.active ? (
                  <button type='button' onClick={() => handleSuspend(u.id)}>
                    Suspend
                  </button>
                ) : (
                  <button type='button' onClick={() => handleActivate(u.id)}>
                    Activate
                  </button>
                )}
                <button type='button' onClick={() => handleDeleteUser(u.id)} className='admin-users-btn admin-users-btn-delete'>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
