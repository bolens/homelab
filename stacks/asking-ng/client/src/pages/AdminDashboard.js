import React from 'react';
import { Link } from 'react-router-dom';
import { useAdmin } from '../context/AdminContext';

export default function AdminDashboard() {
  const { admin } = useAdmin();
  return (
    <div style={{ padding: 32 }}>
      <h2>Admin Dashboard</h2>
      <ul>
        <li>
          <Link to='/admin/users'>Manage Users</Link>
        </li>
        <li>
          <Link to='/admin/polls'>Manage Polls</Link>
        </li>
        <li>
          <Link to='/admin/audit-logs'>Audit Logs</Link>
        </li>
        <li>
          <Link to='/admin/export'>Export Data</Link>
        </li>
        <li>
          <Link to='/admin/status'>System Status</Link>
        </li>
        {admin && admin.role === 'superadmin' && (
          <li>
            <Link to='/admin/impersonate'>Impersonate User</Link>
          </li>
        )}
      </ul>
    </div>
  );
}
