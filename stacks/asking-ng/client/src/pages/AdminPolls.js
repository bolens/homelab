import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAdmin } from '../context/AdminContext';
import { apiFetch } from '../http';

export default function AdminPolls() {
  const { admin } = useAdmin();
  const navigate = useNavigate();
  const [polls, setPolls] = useState([]);
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [sortBy, setSortBy] = useState('id');
  const [sortDir, setSortDir] = useState('asc');
  const [selected, setSelected] = useState([]);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [newPoll, setNewPoll] = useState({ question: '', options: '' });
  const [editId, setEditId] = useState(null);
  const [editPoll, setEditPoll] = useState({ question: '', options: '' });
  const [detailsId, setDetailsId] = useState(null);
  const [detailsPoll, setDetailsPoll] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  useEffect(() => {
    apiFetch('admin/polls')
      .then((data) => setPolls(data.polls))
      .catch(() => setError('Failed to load polls'));
  }, [refresh]);

  const handleCreatePoll = async (e) => {
    e.preventDefault();
    setError('');
    if (!newPoll.question || !newPoll.options) return setError('Question and options required');
    const optionsArr = newPoll.options
      .split(',')
      .map((opt) => opt.trim())
      .filter(Boolean);
    if (optionsArr.length < 2) return setError('At least 2 options required');
    try {
      await apiFetch('admin/polls', { method: 'POST', body: { question: newPoll.question, options: optionsArr } });
      setNewPoll({ question: '', options: '' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to create poll');
    }
  };

  const handleShowDetails = async (id) => {
    setDetailsId(id);
    setDetailsPoll(null);
    setDetailsLoading(true);
    setError('');
    try {
      const data = await apiFetch(`admin/polls/${id}`);
      setDetailsPoll(data.poll);
    } catch {
      setError('Failed to load poll details');
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleCloseDetails = () => {
    setDetailsId(null);
    setDetailsPoll(null);
  };

  const handleEdit = (poll) => {
    setEditId(poll.id);
    setEditPoll({
      question: poll.question,
      options: poll.options ? poll.options.join(', ') : '',
    });
    setError('');
    setSuccess('');
  };

  const handleCancelEdit = () => {
    setEditId(null);
    setEditPoll({ question: '', options: '' });
  };

  const handleSaveEdit = async (id) => {
    if (!editPoll.question || !editPoll.options) {
      setError('Question and options required');
      return;
    }
    const optionsArr = editPoll.options
      .split(',')
      .map((opt) => opt.trim())
      .filter(Boolean);
    if (optionsArr.length < 2) {
      setError('At least 2 options required');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await apiFetch(`admin/polls/${id}`, {
        method: 'PATCH',
        body: { question: editPoll.question, options: optionsArr },
      });
      setSuccess('Poll updated successfully');
      setEditId(null);
      setEditPoll({ question: '', options: '' });
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to update poll');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this poll?')) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await apiFetch(`admin/polls/${id}`, { method: 'DELETE' });
      setSuccess('Poll deleted');
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to delete poll');
    } finally {
      setLoading(false);
    }
  };

  const handleResetVotes = async (id) => {
    if (!window.confirm('Reset all votes for this poll?')) return;
    setLoading(true);
    try {
      await apiFetch(`admin/polls/${id}/reset-votes`, { method: 'POST', body: {} });
      setSuccess('Votes reset');
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to reset votes');
    } finally {
      setLoading(false);
    }
  };

  const handleArchive = async (id) => {
    if (!window.confirm('Archive this poll?')) return;
    setLoading(true);
    try {
      await apiFetch(`admin/polls/${id}/archive`, { method: 'PATCH', body: {} });
      setSuccess('Poll archived');
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to archive');
    } finally {
      setLoading(false);
    }
  };

  const handleUnarchive = async (id) => {
    if (!window.confirm('Unarchive this poll?')) return;
    setLoading(true);
    try {
      await apiFetch(`admin/polls/${id}/unarchive`, { method: 'PATCH', body: {} });
      setSuccess('Poll unarchived');
      setRefresh((r) => r + 1);
    } catch {
      setError('Failed to unarchive');
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (id) => {
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
  };

  const handleBulk = async (action) => {
    const msgs = {
      archive: 'Archive selected polls?',
      unarchive: 'Unarchive selected polls?',
      reset: 'Reset votes for selected polls?',
      delete: 'Delete selected polls?',
    };
    if (!window.confirm(msgs[action])) return;
    setLoading(true);
    setError('');
    for (const id of selected) {
      try {
        if (action === 'archive') await apiFetch(`admin/polls/${id}/archive`, { method: 'PATCH', body: {} });
        if (action === 'unarchive') await apiFetch(`admin/polls/${id}/unarchive`, { method: 'PATCH', body: {} });
        if (action === 'reset') await apiFetch(`admin/polls/${id}/reset-votes`, { method: 'POST', body: {} });
        if (action === 'delete') await apiFetch(`admin/polls/${id}`, { method: 'DELETE' });
      } catch {
        setError(`Bulk failed on ${id}`);
      }
    }
    setSelected([]);
    setRefresh((r) => r + 1);
    setLoading(false);
  };

  let filteredPolls = polls.filter(
    (p) => p.question.toLowerCase().includes(search.toLowerCase()) || String(p.id) === search
  );

  filteredPolls = filteredPolls.sort((a, b) => {
    let v1 = a[sortBy];
    let v2 = b[sortBy];
    if (typeof v1 === 'string') v1 = v1.toLowerCase();
    if (typeof v2 === 'string') v2 = v2.toLowerCase();
    if (v1 < v2) return sortDir === 'asc' ? -1 : 1;
    if (v1 > v2) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const totalPages = Math.max(1, Math.ceil(filteredPolls.length / rowsPerPage));
  const pagedPolls = filteredPolls.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  if (!admin || (admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return <div style={{ padding: 32, color: 'red' }}>Access denied: Only admin or superadmin can manage polls.</div>;
  }

  return (
    <div style={{ padding: 32 }}>
      <h3>Polls</h3>
      {loading && <div>Loading...</div>}
      {success && <div style={{ color: 'green' }}>{success}</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}

      <form onSubmit={handleCreatePoll} style={{ marginBottom: 16 }} aria-label='Create poll form'>
        <b>Create Poll:</b>
        <input
          placeholder='Question'
          value={newPoll.question}
          onChange={(e) => setNewPoll({ ...newPoll, question: e.target.value })}
          style={{ marginLeft: 8 }}
          required
        />
        <input
          placeholder='Options (comma separated)'
          value={newPoll.options}
          onChange={(e) => setNewPoll({ ...newPoll, options: e.target.value })}
          style={{ marginLeft: 8, width: 280 }}
          required
        />
        <button type='submit' style={{ marginLeft: 8 }}>
          Create
        </button>
      </form>

      <div style={{ marginBottom: 12 }}>
        <input placeholder='Search' value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginRight: 8 }} />
        <button type='button' onClick={() => setRefresh((r) => r + 1)}>
          Refresh
        </button>
      </div>

      <div style={{ marginBottom: 12 }}>
        <b>Bulk:</b>
        <button type='button' disabled={!selected.length || loading} onClick={() => handleBulk('archive')} style={{ marginLeft: 4 }}>
          Archive
        </button>
        <button type='button' disabled={!selected.length || loading} onClick={() => handleBulk('unarchive')} style={{ marginLeft: 4 }}>
          Unarchive
        </button>
        <button type='button' disabled={!selected.length || loading} onClick={() => handleBulk('reset')} style={{ marginLeft: 4 }}>
          Reset votes
        </button>
        <button type='button' disabled={!selected.length || loading} onClick={() => handleBulk('delete')} style={{ marginLeft: 4 }}>
          Delete
        </button>
        <span style={{ marginLeft: 8 }}>{selected.length} selected</span>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Question</th>
            <th>Options</th>
            <th>Archived</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {pagedPolls.map((p) => (
            <tr key={p.id}>
              <td>
                <input type='checkbox' checked={selected.includes(p.id)} onChange={() => handleSelect(p.id)} /> {p.id}
              </td>
              <td>
                {editId === p.id ? (
                  <input value={editPoll.question} onChange={(e) => setEditPoll({ ...editPoll, question: e.target.value })} />
                ) : (
                  p.question
                )}
              </td>
              <td>
                {editId === p.id ? (
                  <input value={editPoll.options} onChange={(e) => setEditPoll({ ...editPoll, options: e.target.value })} style={{ width: 240 }} />
                ) : (
                  Array.isArray(p.options) ? p.options.join(', ') : ''
                )}
              </td>
              <td>{p.archived ? 'Yes' : 'No'}</td>
              <td>
                <button type='button' onClick={() => handleShowDetails(p.id)} disabled={loading || editId === p.id}>
                  Details
                </button>
                {editId === p.id ? (
                  <>
                    <button type='button' onClick={() => handleSaveEdit(p.id)} disabled={loading}>
                      Save
                    </button>
                    <button type='button' onClick={handleCancelEdit} disabled={loading}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button type='button' onClick={() => handleEdit(p)} disabled={loading}>
                      Edit
                    </button>
                    {p.archived ? (
                      <button type='button' onClick={() => handleUnarchive(p.id)} disabled={loading}>
                        Unarchive
                      </button>
                    ) : (
                      <button type='button' onClick={() => handleArchive(p.id)} disabled={loading}>
                        Archive
                      </button>
                    )}
                    <button type='button' onClick={() => handleResetVotes(p.id)} disabled={loading}>
                      Reset votes
                    </button>
                    <button type='button' onClick={() => handleDelete(p.id)} disabled={loading}>
                      Delete
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 12 }}>
        <button type='button' disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Prev
        </button>
        <span style={{ margin: '0 8px' }}>
          Page {page} of {totalPages}
        </span>
        <button type='button' disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
          Next
        </button>
        <label style={{ marginLeft: 16 }}>
          Rows/page
          <select value={rowsPerPage} onChange={(e) => { setRowsPerPage(Number(e.target.value)); setPage(1); }} style={{ marginLeft: 4 }}>
            {[5, 10, 20, 50].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {detailsId && (
        <div
          role='dialog'
          aria-modal='true'
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onKeyDown={(e) => e.key === 'Escape' && handleCloseDetails()}
        >
          <div style={{ background: '#fff', padding: 24, maxWidth: 480, maxHeight: '90vh', overflow: 'auto' }}>
            <h4>Poll details</h4>
            {detailsLoading || !detailsPoll ? (
              <div>Loading...</div>
            ) : (
              <>
                <div>
                  <b>ID:</b> {detailsPoll.id}
                </div>
                <div>
                  <b>Question:</b> {detailsPoll.question}
                </div>
                <div>
                  <b>Archived:</b> {detailsPoll.archived ? 'Yes' : 'No'}
                </div>
                <ul>
                  {detailsPoll.options &&
                    detailsPoll.options.map((opt, i) => (
                      <li key={i}>
                        {opt} ({detailsPoll.votes && detailsPoll.votes[i] != null ? detailsPoll.votes[i] : 0} votes)
                      </li>
                    ))}
                </ul>
                <button type='button' style={{ marginTop: 8 }} onClick={handleCloseDetails}>
                  Close
                </button>
                <button
                  type='button'
                  style={{ marginTop: 8, marginLeft: 8 }}
                  onClick={() => {
                    handleCloseDetails();
                    setTimeout(() => navigate(`/admin/audit-logs?target=${encodeURIComponent(detailsPoll.id)}`), 50);
                  }}
                >
                  Audit logs
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
