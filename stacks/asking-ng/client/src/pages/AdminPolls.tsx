import { adminPollWriteBodySchema } from '@asking-ng/contracts/admin';
import { useNavigate } from '@tanstack/react-router';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useMaxWidth600 } from '../hooks/useMaxWidth600';
import { apiFetch } from '../http';
import { useLocaleTag, useT } from '../i18n/I18nContext';
import { formatLocaleInteger } from '../lib/formatLocaleDisplay';
import { Button, cx, Select, VisuallyHidden } from '../ui';
import { errMsg } from '../utils/errMsg';
import { zodErrorSummary } from '../utils/zodForm';
import { useAdminWebSocket } from '../wsClient';

type AdminPollRow = {
  id: string;
  question: string;
  options?: string[];
  archived?: boolean;
  voting_paused?: boolean;
};

type AdminPollDetails = AdminPollRow & { votes?: (number | null)[] };

type PollSortKey = 'id' | 'question' | 'archived';
const SIMULATED_POLL_ID_PREFIX = 'sim_';

function isSimulatedPollId(id: string): boolean {
  return id.toLowerCase().startsWith(SIMULATED_POLL_ID_PREFIX);
}

export default function AdminPolls() {
  const t = useT();
  const localeTag = useLocaleTag();
  useDocumentTitle(t('admin.docTitlePolls'));
  const { admin } = useAdmin();
  const navigate = useNavigate();
  const [polls, setPolls] = useState<AdminPollRow[]>([]);
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [sortBy, setSortBy] = useState<PollSortKey>('id');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [hideSimulation, setHideSimulation] = useState(false);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [newPoll, setNewPoll] = useState({ question: '', options: '' });
  const [editId, setEditId] = useState<string | null>(null);
  const [editPoll, setEditPoll] = useState({ question: '', options: '' });
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [detailsPoll, setDetailsPoll] = useState<AdminPollDetails | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const hasAutoRevealedBulkActionsRef = useRef(false);
  const detailsTitleRef = useRef<HTMLHeadingElement>(null);
  const detailsDialogRef = useRef<HTMLDivElement>(null);
  const preDetailsFocusRef = useRef<HTMLElement | null>(null);

  const clearMessages = useCallback(() => {
    setError('');
    setSuccess('');
  }, []);

  const bumpPollListFromWebSocket = useCallback(() => {
    setRefresh((r) => r + 1);
  }, []);

  useAdminWebSocket({ onPollUpdate: bumpPollListFromWebSocket });

  const handleCloseDetails = useCallback(() => {
    setDetailsId(null);
    setDetailsPoll(null);
    const restore = preDetailsFocusRef.current;
    preDetailsFocusRef.current = null;
    window.requestAnimationFrame(() => {
      if (restore?.focus) restore.focus();
    });
  }, []);

  useEffect(() => {
    if (!detailsId) return;
    const id = window.requestAnimationFrame(() => {
      detailsTitleRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(id);
  }, [detailsId]);

  useEffect(() => {
    if (!detailsId) return;
    const onDocumentKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCloseDetails();
    };
    document.addEventListener('keydown', onDocumentKeyDown);
    return () => document.removeEventListener('keydown', onDocumentKeyDown);
  }, [detailsId, handleCloseDetails]);

  useEffect(() => {
    if (!detailsId) return;
    const root = detailsDialogRef.current;
    if (!root) return;

    const focusables = (): HTMLElement[] =>
      Array.from(
        root.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)',
        ),
      );

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        handleCloseDetails();
        return;
      }
      if (e.key !== 'Tab') return;
      const nodes = focusables();
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    root.addEventListener('keydown', onKeyDown);
    return () => root.removeEventListener('keydown', onKeyDown);
  }, [detailsId, detailsLoading, detailsPoll, handleCloseDetails]);

  useEffect(() => {
    apiFetch('admin/polls')
      .then((data) => setPolls((data as { polls: AdminPollRow[] }).polls ?? []))
      .catch((err) => setError(errMsg(err, t('admin.polls.errLoad'))));
  }, [refresh, t]);

  useEffect(() => {
    if (selected.length === 0 || detailsId) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setSelected([]);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [selected.length, detailsId]);

  const parsePollWrite = (question: string, optionsCsv: string) => {
    const options = optionsCsv
      .split(',')
      .map((opt) => opt.trim())
      .filter(Boolean);
    return adminPollWriteBodySchema.safeParse({ question, options });
  };

  const handleSortClick = (key: PollSortKey) => {
    if (sortBy === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortBy(key);
      setSortDir('asc');
    }
  };

  const sortAriaValue = (key: PollSortKey): 'ascending' | 'descending' | 'none' => {
    if (sortBy !== key) return 'none';
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const sortIndicator = (key: PollSortKey) => {
    if (sortBy !== key) return '';
    return sortDir === 'asc' ? ' ▲' : ' ▼';
  };

  const handleCreatePoll = async (e: React.FormEvent) => {
    e.preventDefault();
    clearMessages();
    const parsed = parsePollWrite(newPoll.question, newPoll.options);
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    try {
      await apiFetch('admin/polls', {
        method: 'POST',
        body: parsed.data,
      });
      setNewPoll({ question: '', options: '' });
      setSuccess(t('admin.polls.successCreated'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errCreate')));
    }
  };

  const handleShowDetails = async (id: string) => {
    preDetailsFocusRef.current = document.activeElement as HTMLElement | null;
    setDetailsId(id);
    setDetailsPoll(null);
    setDetailsLoading(true);
    setError('');
    try {
      const data = (await apiFetch(`admin/polls/${id}`)) as { poll: AdminPollDetails };
      setDetailsPoll(data.poll);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errDetails')));
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleEdit = (poll: AdminPollRow) => {
    clearMessages();
    setEditId(poll.id);
    setEditPoll({
      question: poll.question,
      options: poll.options ? poll.options.join(', ') : '',
    });
  };

  const handleCancelEdit = () => {
    setEditId(null);
    setEditPoll({ question: '', options: '' });
  };

  const handleSaveEdit = async (id: string) => {
    const parsed = parsePollWrite(editPoll.question, editPoll.options);
    if (!parsed.success) {
      setError(zodErrorSummary(parsed.error));
      return;
    }
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}`, {
        method: 'PATCH',
        body: parsed.data,
      });
      setSuccess(t('admin.polls.successUpdated'));
      setEditId(null);
      setEditPoll({ question: '', options: '' });
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errUpdate')));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(t('admin.polls.confirmDelete'))) return;
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}`, { method: 'DELETE' });
      setSuccess(t('admin.polls.successDeleted'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errDelete')));
    } finally {
      setLoading(false);
    }
  };

  const handleResetVotes = async (id: string) => {
    if (!window.confirm(t('admin.polls.confirmResetVotes'))) return;
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}/reset-votes`, { method: 'POST', body: {} });
      setSuccess(t('admin.polls.successVotesReset'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errResetVotes')));
    } finally {
      setLoading(false);
    }
  };

  const handleArchive = async (id: string) => {
    if (!window.confirm(t('admin.polls.confirmArchive'))) return;
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}/archive`, { method: 'PATCH', body: {} });
      setSuccess(t('admin.polls.successArchived'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errArchive')));
    } finally {
      setLoading(false);
    }
  };

  const handleUnarchive = async (id: string) => {
    if (!window.confirm(t('admin.polls.confirmUnarchive'))) return;
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}/unarchive`, { method: 'PATCH', body: {} });
      setSuccess(t('admin.polls.successUnarchived'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, t('admin.polls.errUnarchive')));
    } finally {
      setLoading(false);
    }
  };

  const handlePauseVoting = async (id: string, pause: boolean) => {
    const confirmMsg = pause ? t('admin.polls.confirmPauseVoting') : t('admin.polls.confirmUnpauseVoting');
    if (!window.confirm(confirmMsg)) return;
    setLoading(true);
    clearMessages();
    try {
      await apiFetch(`admin/polls/${id}/${pause ? 'pause' : 'unpause'}`, { method: 'PATCH', body: {} });
      setSuccess(pause ? t('admin.polls.successPausedVoting') : t('admin.polls.successUnpausedVoting'));
      setRefresh((r) => r + 1);
    } catch (err) {
      setError(errMsg(err, pause ? t('admin.polls.errPauseVoting') : t('admin.polls.errUnpauseVoting')));
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (id: string) => {
    const selectingFirst = selected.length === 0 && !selected.includes(id);
    setSelected((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]));
    if (!selectingFirst || hasAutoRevealedBulkActionsRef.current || typeof window === 'undefined')
      return;
    const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
    const narrowViewport = window.matchMedia('(max-width: 900px)').matches;
    if (!coarsePointer && !narrowViewport) return;
    hasAutoRevealedBulkActionsRef.current = true;
    window.requestAnimationFrame(() => {
      window.scrollBy({ top: 120, behavior: 'smooth' });
    });
  };

  const handleBulk = async (action: 'archive' | 'unarchive' | 'reset' | 'delete') => {
    const msgs: Record<typeof action, string> = {
      archive: t('admin.polls.confirmBulkArchive'),
      unarchive: t('admin.polls.confirmBulkUnarchive'),
      reset: t('admin.polls.confirmBulkReset'),
      delete: t('admin.polls.confirmBulkDelete'),
    };
    if (!window.confirm(msgs[action])) return;
    setLoading(true);
    clearMessages();
    for (const id of selected) {
      try {
        if (action === 'archive')
          await apiFetch(`admin/polls/${id}/archive`, { method: 'PATCH', body: {} });
        if (action === 'unarchive')
          await apiFetch(`admin/polls/${id}/unarchive`, { method: 'PATCH', body: {} });
        if (action === 'reset')
          await apiFetch(`admin/polls/${id}/reset-votes`, { method: 'POST', body: {} });
        if (action === 'delete') await apiFetch(`admin/polls/${id}`, { method: 'DELETE' });
      } catch (err) {
        setError(errMsg(err, t('admin.polls.errBulk', { id })));
        setSelected([]);
        setRefresh((r) => r + 1);
        setLoading(false);
        return;
      }
    }
    setSelected([]);
    setSuccess(t('admin.polls.successBulkDone'));
    setRefresh((r) => r + 1);
    setLoading(false);
  };

  const filteredPolls = useMemo(() => {
    const list = polls.filter((p) => {
      if (hideSimulation && isSimulatedPollId(p.id)) return false;
      return p.question.toLowerCase().includes(search.toLowerCase()) || String(p.id) === search;
    });
    return [...list].sort((a, b) => {
      if (sortBy === 'archived') {
        const diff = Number(!!a.archived) - Number(!!b.archived);
        if (diff !== 0) return sortDir === 'asc' ? diff : -diff;
      } else if (sortBy === 'id') {
        const cmp = a.id.localeCompare(b.id, undefined, { numeric: true, sensitivity: 'base' });
        if (cmp !== 0) return sortDir === 'asc' ? cmp : -cmp;
      } else {
        const v1 = a.question.toLowerCase();
        const v2 = b.question.toLowerCase();
        if (v1 < v2) return sortDir === 'asc' ? -1 : 1;
        if (v1 > v2) return sortDir === 'asc' ? 1 : -1;
      }
      return a.id.localeCompare(b.id, undefined, { numeric: true, sensitivity: 'base' });
    });
  }, [polls, hideSimulation, search, sortBy, sortDir]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(filteredPolls.length / rowsPerPage)),
    [filteredPolls.length, rowsPerPage],
  );

  const pagedPolls = useMemo(
    () => filteredPolls.slice((page - 1) * rowsPerPage, page * rowsPerPage),
    [filteredPolls, page, rowsPerPage],
  );

  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    setPage((p) => Math.min(Math.max(1, p), totalPages));
  }, [totalPages]);

  const narrow600 = useMaxWidth600();
  const mobileStickyBulkActive = narrow600 && selected.length > 0;

  const shownStr = formatLocaleInteger(filteredPolls.length, localeTag);
  const totalStr = formatLocaleInteger(polls.length, localeTag);

  if (!admin || (admin.role !== 'mod' && admin.role !== 'admin' && admin.role !== 'superadmin')) {
    return (
      <div className='polls-page-container-error' role='alert'>
        {t('admin.polls.accessDenied')}
      </div>
    );
  }

  return (
    <div
      className={`polls-page-container admin-cq-root${selected.length > 0 ? ' has-mobile-bulk-actions' : ''}`}
    >
      <header className='admin-page-header'>
        <h1 className='admin-page-title'>{t('admin.polls.heading')}</h1>
        <p className='admin-page-subtitle'>
          {t('admin.polls.pageSubtitle', { shown: shownStr, total: totalStr })}
        </p>
      </header>
      {selected.length > 0 ? (
        <a
          href={mobileStickyBulkActive ? '#admin-polls-mobile-bulk' : '#admin-polls-bulk-actions'}
          className='admin-jump-link'
        >
          {t('admin.polls.skipToBulk')}
        </a>
      ) : null}
      {loading ? (
        <div className='poll-status poll-status-loading' role='status' aria-live='polite'>
          {t('admin.polls.loading')}
        </div>
      ) : null}
      {success ? (
        <div className='poll-status poll-status-success' role='status' aria-live='polite'>
          {success}
        </div>
      ) : null}
      {error ? (
        <div className='poll-status poll-status-error' role='alert'>
          {error}
        </div>
      ) : null}

      <form
        onSubmit={handleCreatePoll}
        className='poll-form poll-form--tight'
        aria-label={t('admin.polls.createFormAria')}
      >
        <b>{t('admin.polls.createLabel')}</b>
        <VisuallyHidden as='label' htmlFor='admin-polls-new-question'>
          {t('admin.polls.labelQuestion')}
        </VisuallyHidden>
        <input
          id='admin-polls-new-question'
          placeholder={t('admin.polls.placeholderQuestion')}
          value={newPoll.question}
          onChange={(e) => setNewPoll({ ...newPoll, question: e.target.value })}
          className='poll-input-question'
          required
        />
        <VisuallyHidden as='label' htmlFor='admin-polls-new-options'>
          {t('admin.polls.labelOptions')}
        </VisuallyHidden>
        <input
          id='admin-polls-new-options'
          placeholder={t('admin.polls.placeholderOptions')}
          value={newPoll.options}
          onChange={(e) => setNewPoll({ ...newPoll, options: e.target.value })}
          className='poll-input-wide'
          required
        />
        <Button type='submit' variant='primary' className='poll-btn'>
          {t('admin.polls.create')}
        </Button>
      </form>

      <div className='polls-search-bar polls-search-bar--tight'>
        <VisuallyHidden as='label' htmlFor='admin-polls-search'>
          {t('admin.polls.searchLabel')}
        </VisuallyHidden>
        <input
          id='admin-polls-search'
          placeholder={t('admin.polls.placeholderSearch')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          aria-label={t('admin.polls.clearSearchAria')}
          onClick={() => setSearch('')}
        >
          {t('admin.polls.clear')}
        </Button>
        <label className='admin-polls-sim-toggle'>
          <input
            type='checkbox'
            checked={hideSimulation}
            onChange={(e) => setHideSimulation(e.target.checked)}
          />{' '}
          {t('admin.polls.hideSimulation')}
        </label>
        <Button type='button' variant='secondary' className='poll-btn' onClick={() => setRefresh((r) => r + 1)}>
          {t('admin.polls.refresh')}
        </Button>
      </div>

      <section
        id='admin-polls-bulk-actions'
        role='region'
        aria-labelledby='admin-polls-bulk-heading'
        className='polls-bulk-actions polls-bulk-actions--tight'
        inert={mobileStickyBulkActive}
      >
        <b id='admin-polls-bulk-heading'>{t('admin.polls.bulkLabel')}</b>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          disabled={!selected.length || loading}
          onClick={() => void handleBulk('archive')}
          aria-label={t('admin.polls.voiceArchiveBulk')}
        >
          {t('admin.polls.archive')}
        </Button>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          disabled={!selected.length || loading}
          onClick={() => void handleBulk('unarchive')}
          aria-label={t('admin.polls.voiceUnarchiveBulk')}
        >
          {t('admin.polls.unarchive')}
        </Button>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          disabled={!selected.length || loading}
          onClick={() => void handleBulk('reset')}
          aria-label={t('admin.polls.voiceResetBulk')}
        >
          {t('admin.polls.resetVotes')}
        </Button>
        <Button
          type='button'
          variant='secondary'
          disabled={!selected.length || loading}
          onClick={() => void handleBulk('delete')}
          className={cx('poll-btn', 'poll-delete-btn')}
          aria-label={t('admin.polls.voiceDeleteBulk')}
        >
          {t('admin.polls.delete')}
        </Button>
        <span className='poll-bulk-selected' role='status' aria-live='polite' aria-atomic='true'>
          {t('admin.polls.selected', { count: formatLocaleInteger(selected.length, localeTag) })}
        </span>
      </section>

      <div className='admin-data-table-wrap'>
        <table className='polls-table'>
          <thead>
            <tr>
              <th scope='col' aria-sort={sortAriaValue('id')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('id')}
                >
                  {t('admin.polls.colId')}
                  {sortIndicator('id')}
                </button>
              </th>
              <th scope='col' aria-sort={sortAriaValue('question')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('question')}
                >
                  {t('admin.polls.colQuestion')}
                  {sortIndicator('question')}
                </button>
              </th>
              <th scope='col'>{t('admin.polls.colOptions')}</th>
              <th scope='col' aria-sort={sortAriaValue('archived')}>
                <button
                  type='button'
                  className='table-sort-btn'
                  onClick={() => handleSortClick('archived')}
                >
                  {t('admin.polls.colArchived')}
                  {sortIndicator('archived')}
                </button>
              </th>
              <th scope='col'>{t('admin.polls.colActions')}</th>
            </tr>
          </thead>
          <tbody>
            {pagedPolls.map((p) => (
              <tr key={p.id}>
                <td>
                  <input
                    type='checkbox'
                    checked={selected.includes(p.id)}
                    onChange={() => handleSelect(p.id)}
                    onKeyDown={(e) => {
                      if ((e.key === ' ' || e.key === 'Spacebar') && e.shiftKey) {
                        e.preventDefault();
                        handleSelect(p.id);
                      }
                    }}
                    aria-label={t('admin.polls.selectPoll', { id: p.id })}
                  />{' '}
                  {p.id}
                </td>
                <td>
                  {editId === p.id ? (
                    <input
                      value={editPoll.question}
                      onChange={(e) => setEditPoll({ ...editPoll, question: e.target.value })}
                      className='poll-input-question'
                      aria-label={t('admin.polls.editQuestionAria')}
                    />
                  ) : (
                    <>
                      {p.question}
                      {isSimulatedPollId(p.id) ? (
                        <span className='admin-sim-badge'>{t('admin.polls.simulationBadge')}</span>
                      ) : null}
                    </>
                  )}
                </td>
                <td>
                  {editId === p.id ? (
                    <input
                      value={editPoll.options}
                      onChange={(e) => setEditPoll({ ...editPoll, options: e.target.value })}
                      className='poll-edit-input-wide'
                      aria-label={t('admin.polls.editOptionsAria')}
                    />
                  ) : Array.isArray(p.options) ? (
                    p.options.join(', ')
                  ) : (
                    ''
                  )}
                </td>
                <td>
                  <span
                    className={
                      p.archived
                        ? 'admin-polls-archive-badge admin-polls-archive-badge--yes'
                        : 'admin-polls-archive-badge'
                    }
                  >
                    {p.archived ? t('admin.polls.yes') : t('admin.polls.no')}
                  </span>
                </td>
                <td>
                  <div className='admin-polls-actions-cell'>
                    <Button
                      type='button'
                      variant='secondary'
                      className='poll-btn'
                      onClick={() => void handleShowDetails(p.id)}
                      disabled={loading || editId === p.id}
                      aria-label={t('admin.polls.voiceDetailsRow', { id: p.id })}
                    >
                      {t('admin.polls.details')}
                    </Button>
                    {editId === p.id ? (
                      <>
                        <Button
                          type='button'
                          variant='secondary'
                          className='poll-btn'
                          onClick={() => void handleSaveEdit(p.id)}
                          disabled={loading}
                          aria-label={t('admin.polls.voiceSaveRow', { id: p.id })}
                        >
                          {t('admin.polls.save')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          className='poll-btn'
                          onClick={handleCancelEdit}
                          disabled={loading}
                          aria-label={t('admin.polls.voiceCancelEditRow', { id: p.id })}
                        >
                          {t('admin.polls.cancel')}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          type='button'
                          variant='secondary'
                          className='poll-btn'
                          onClick={() => handleEdit(p)}
                          disabled={loading}
                          aria-label={t('admin.polls.voiceEditRow', { id: p.id })}
                        >
                          {t('admin.polls.edit')}
                        </Button>
                        {p.archived ? (
                          <Button
                            type='button'
                            variant='secondary'
                            className='poll-btn'
                            onClick={() => void handleUnarchive(p.id)}
                            disabled={loading}
                            aria-label={t('admin.polls.voiceUnarchiveRow', { id: p.id })}
                          >
                            {t('admin.polls.unarchive')}
                          </Button>
                        ) : (
                          <Button
                            type='button'
                            variant='secondary'
                            className='poll-btn'
                            onClick={() => void handleArchive(p.id)}
                            disabled={loading}
                            aria-label={t('admin.polls.voiceArchiveRow', { id: p.id })}
                          >
                            {t('admin.polls.archive')}
                          </Button>
                        )}
                        <Button
                          type='button'
                          variant='secondary'
                          className='poll-btn'
                          onClick={() => void handleResetVotes(p.id)}
                          disabled={loading}
                          aria-label={t('admin.polls.voiceResetVotesRow', { id: p.id })}
                        >
                          {t('admin.polls.resetVotes')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          className='poll-btn'
                          onClick={() => void handlePauseVoting(p.id, !p.voting_paused)}
                          disabled={loading || !!p.archived}
                        >
                          {p.voting_paused ? t('admin.polls.unpauseVoting') : t('admin.polls.pauseVoting')}
                        </Button>
                        <Button
                          type='button'
                          variant='secondary'
                          onClick={() => void handleDelete(p.id)}
                          disabled={loading}
                          className={cx('poll-btn', 'poll-delete-btn')}
                          aria-label={t('admin.polls.voiceDeleteRow', { id: p.id })}
                        >
                          {t('admin.polls.delete')}
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className='polls-pagination-bar'>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          disabled={page <= 1}
          aria-label={t('admin.polls.prevAria')}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          {t('admin.polls.prev')}
        </Button>
        <span className='poll-pagination-pageinfo'>
          {t('admin.polls.pageOf', {
            page: formatLocaleInteger(page, localeTag),
            total: formatLocaleInteger(totalPages, localeTag),
          })}
        </span>
        <Button
          type='button'
          variant='secondary'
          className='poll-btn'
          disabled={page >= totalPages}
          aria-label={t('admin.polls.nextAria')}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
        >
          {t('admin.polls.next')}
        </Button>
        <label className='poll-pagination-label'>
          {t('admin.polls.rowsPerPage')}
          <Select
            value={String(rowsPerPage)}
            onChange={(e) => {
              setRowsPerPage(Number(e.target.value));
              setPage(1);
            }}
          >
            {[5, 10, 20, 50].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </Select>
        </label>
      </div>

      {detailsId && (
        <div
          ref={detailsDialogRef}
          role='dialog'
          aria-modal='true'
          aria-labelledby='admin-poll-details-title'
          className='poll-modal-overlay'
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) handleCloseDetails();
          }}
        >
          <div
            className='poll-modal-content poll-modal-content--scroll'
            onMouseDown={(e) => e.stopPropagation()}
          >
            <h2
              id='admin-poll-details-title'
              className='poll-modal-title'
              ref={detailsTitleRef}
              tabIndex={-1}
            >
              {t('admin.polls.modalTitle')}
            </h2>
            <div className='poll-modal-actions poll-modal-actions--start'>
              <Button type='button' variant='secondary' className='poll-btn' onClick={handleCloseDetails}>
                {t('admin.polls.close')}
              </Button>
              {!detailsLoading && detailsPoll ? (
                <Button
                  type='button'
                  variant='secondary'
                  className='poll-btn'
                  onClick={() => {
                    const targetId = detailsPoll.id;
                    handleCloseDetails();
                    window.setTimeout(
                      () =>
                        navigate({
                          to: '/admin/audit-logs',
                          search: { target: targetId, limit: undefined },
                        }),
                      50,
                    );
                  }}
                >
                  {t('admin.polls.auditLogs')}
                </Button>
              ) : null}
            </div>
            {detailsLoading || !detailsPoll ? (
              <div className='poll-status poll-status-loading' role='status' aria-live='polite'>
                {t('admin.polls.loading')}
              </div>
            ) : (
              <>
                <div>
                  <b>{t('admin.polls.detailId')}</b> {detailsPoll.id}
                </div>
                <div>
                  <b>{t('admin.polls.detailQuestion')}</b> {detailsPoll.question}
                </div>
                <div>
                  <b>{t('admin.polls.detailArchived')}</b>{' '}
                  {detailsPoll.archived ? t('admin.polls.yes') : t('admin.polls.no')}
                </div>
                <ul>
                  {detailsPoll.options &&
                    detailsPoll.options.map((opt, i) => (
                      <li key={i}>
                        {t('admin.polls.detailOptionLine', {
                          option: opt,
                          count: formatLocaleInteger(
                            detailsPoll.votes && detailsPoll.votes[i] != null
                              ? Number(detailsPoll.votes[i])
                              : 0,
                            localeTag,
                          ),
                        })}
                      </li>
                    ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}
      {selected.length > 0 ? (
        <section
          id='admin-polls-mobile-bulk'
          role='region'
          aria-labelledby='admin-polls-mobile-bulk-heading'
          className='admin-mobile-bulk-actions'
        >
          <VisuallyHidden as='h2' id='admin-polls-mobile-bulk-heading'>
            {t('admin.polls.bulkLabel')}
          </VisuallyHidden>
          <span
            className='admin-mobile-bulk-selected'
            role='status'
            aria-live='polite'
            aria-atomic='true'
          >
            {t('admin.polls.selected', { count: formatLocaleInteger(selected.length, localeTag) })}
          </span>
          <div className='admin-mobile-bulk-buttons'>
            <Button
              type='button'
              variant='secondary'
              disabled={loading}
              onClick={() => void handleBulk('archive')}
              className='poll-btn'
              aria-label={t('admin.polls.voiceArchiveBulk')}
            >
              {t('admin.polls.archive')}
            </Button>
            <Button
              type='button'
              variant='secondary'
              disabled={loading}
              onClick={() => void handleBulk('unarchive')}
              className='poll-btn'
              aria-label={t('admin.polls.voiceUnarchiveBulk')}
            >
              {t('admin.polls.unarchive')}
            </Button>
            <Button
              type='button'
              variant='secondary'
              disabled={loading}
              onClick={() => void handleBulk('reset')}
              className='poll-btn'
              aria-label={t('admin.polls.voiceResetBulk')}
            >
              {t('admin.polls.resetVotes')}
            </Button>
            <Button
              type='button'
              variant='secondary'
              disabled={loading}
              onClick={() => void handleBulk('delete')}
              className={cx('poll-btn', 'poll-delete-btn')}
              aria-label={t('admin.polls.voiceDeleteBulk')}
            >
              {t('admin.polls.delete')}
            </Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
