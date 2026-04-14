import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import Navbar from './components/Navbar';
import Home from './pages/Home';
import Poll from './pages/Poll';

import AdminDashboard from './pages/AdminDashboard';
import AdminUsers from './pages/AdminUsers';
import AdminPolls from './pages/AdminPolls';
import AdminAuditLogs from './pages/AdminAuditLogs';
import AdminLogin from './pages/AdminLogin';
import AdminExport from './pages/AdminExport';
import AdminStatus from './pages/AdminStatus';
import AdminImpersonate from './pages/AdminImpersonate';

function isAdminAuthed() {
  return !!localStorage.getItem('adminToken');
}

function App() {
  return (
    <div style={{ textAlign: 'center' }}>
      <Navbar />
      <Router>
        <Routes>
          <Route path='/admin/login' element={<AdminLogin />} />
          <Route path='/admin' element={isAdminAuthed() ? <AdminDashboard /> : <AdminLogin />} />
          <Route path='/admin/users' element={isAdminAuthed() ? <AdminUsers /> : <AdminLogin />} />
          <Route path='/admin/polls' element={isAdminAuthed() ? <AdminPolls /> : <AdminLogin />} />
          <Route path='/admin/audit-logs' element={isAdminAuthed() ? <AdminAuditLogs /> : <AdminLogin />} />
          <Route path='/admin/export' element={isAdminAuthed() ? <AdminExport /> : <AdminLogin />} />
          <Route path='/admin/status' element={isAdminAuthed() ? <AdminStatus /> : <AdminLogin />} />
          <Route path='/admin/impersonate' element={isAdminAuthed() ? <AdminImpersonate /> : <AdminLogin />} />
          <Route path='/:id' element={<Poll />} />
          <Route path='/' element={<Home />} />
        </Routes>
      </Router>
    </div>
  );
}

export default App;
