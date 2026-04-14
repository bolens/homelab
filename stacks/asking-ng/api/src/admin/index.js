const express = require('express');
const { Op, QueryTypes } = require('sequelize');
const router = express.Router();
const sequelize = require('../connections');
const User = require('../models/user.sequelize');
const Poll = require('../model/Poll');
const Vote = require('../model/Vote');
const AuditLog = require('../models/auditlog.sequelize');
const { generateToken, comparePassword, hashPassword } = require('../utils/auth');
const { Parser } = require('json2csv');
const randomId = require('../helpers/randomId');

async function aggregateVotesForPoll(pollId, options) {
	const rows = await sequelize.query(
		'SELECT option, count(option)::int AS "voteCount" FROM votes WHERE "pollId" = :pollId GROUP BY option',
		{ replacements: { pollId }, type: QueryTypes.SELECT }
	);
	const counts = {};
	for (const row of rows) counts[row.option] = Number(row.voteCount);
	return options.map((opt) => counts[opt] || 0);
}

async function toAdminPollShape(p) {
	const j = p.toJSON ? p.toJSON() : p;
	const votes = await aggregateVotesForPoll(j.id, j.options || []);
	return {
		id: j.id,
		question: j.title,
		options: j.options,
		archived: !!j.archived,
		votes,
	};
}
// POST /admin/impersonate/:id - Admin impersonates a user (returns JWT)
router.post('/impersonate/:id', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const user = await User.findByPk(id);
	if (!user) return res.status(404).json({ error: 'User not found' });
	const token = generateToken(user);
	await logAdminAction('impersonate_user', 'admin', id, null);
	res.json({ token });
});
// GET /admin/status - System status and stats
router.get('/status', requireAdminAuth, async (req, res) => {
	const userCount = await User.count();
	const activeUserCount = await User.count({ where: { active: true } });
	const pollCount = await Poll.count();
	const archivedPollCount = await Poll.count({ where: { archived: true } });
	const recentAuditCount = await AuditLog.count({
		where: { createdAt: { [Op.gte]: new Date(Date.now() - 24 * 60 * 60 * 1000) } },
	});
	res.json({
		users: { total: userCount, active: activeUserCount },
		polls: { total: pollCount, archived: archivedPollCount },
		auditLogs: { last24h: recentAuditCount },
		timestamp: new Date().toISOString()
	});
});
// Helper to export data as JSON or CSV
function exportData(res, data, fields, format, filename) {
	if (format === 'csv') {
		const parser = new Parser({ fields });
		const csv = parser.parse(data);
		res.header('Content-Type', 'text/csv');
		res.attachment(filename + '.csv');
		res.send(csv);
	} else {
		res.header('Content-Type', 'application/json');
		res.attachment(filename + '.json');
		res.send(JSON.stringify(data, null, 2));
	}
}
// GET /admin/export/users - Export users
router.get('/export/users', requireAdminAuth, async (req, res) => {
	const format = req.query.format === 'csv' ? 'csv' : 'json';
	const users = await User.findAll({ attributes: ['id', 'homelab-user', 'role', 'active'] });
	exportData(res, users.map(u => u.toJSON()), ['id', 'homelab-user', 'role', 'active'], format, 'users');
});

// GET /admin/export/polls - Export polls
router.get('/export/polls', requireAdminAuth, async (req, res) => {
	const format = req.query.format === 'csv' ? 'csv' : 'json';
	const rows = await Poll.findAll();
	const polls = await Promise.all(rows.map((p) => toAdminPollShape(p)));
	exportData(res, polls, ['id', 'question', 'options', 'votes', 'archived'], format, 'polls');
});

// GET /admin/export/audit-logs - Export audit logs
router.get('/export/audit-logs', requireAdminAuth, async (req, res) => {
	const format = req.query.format === 'csv' ? 'csv' : 'json';
	const logs = await AuditLog.findAll();
	exportData(res, logs.map(l => l.toJSON()), ['id', 'action', 'actor', 'target', 'details', 'createdAt'], format, 'audit_logs');
});
// POST /admin/change-password - Admin changes own password
router.post('/change-password', requireAdminAuth, async (req, res) => {
	const { currentPassword, newPassword } = req.body;
	if (!currentPassword || !newPassword) return res.status(400).json({ error: 'Current and new password required' });
	// Find admin user (assume homelab-user 'admin' or first admin)
	const adminUser = await User.findOne({ where: { role: 'admin' } });
	if (!adminUser) return res.status(404).json({ error: 'Admin user not found' });
	if (!comparePassword(currentPassword, adminUser.password)) {
		return res.status(401).json({ error: 'Invalid current password' });
	}
	adminUser.password = hashPassword(newPassword);
	await adminUser.save();
	await logAdminAction('change_admin_password', 'admin', adminUser.id, null);
	res.json({ message: 'Password updated' });
});

// Simple token-based admin authentication middleware
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || 'changeme';
function requireAdminAuth(req, res, next) {
	const token = req.headers['x-admin-token'];
	if (token === ADMIN_TOKEN) {
		return next();
	}
	res.status(401).json({ error: 'Unauthorized' });
}

// GET /admin/me — validate token for admin UI login
router.get('/me', requireAdminAuth, (req, res) => {
	res.json({ admin: { id: 0, homelab-user: 'admin', role: 'superadmin' } });
});

// Audit log utility
async function logAdminAction(action, actor, target, details) {
  await AuditLog.create({ action, actor, target, details });
}

// In-memory signup toggle (replace with DB or config in production)
let signupsEnabled = true;

// GET /admin/signups - Get signup status
router.get('/signups', requireAdminAuth, (req, res) => {
	res.json({ enabled: signupsEnabled });
});

// POST /admin/signups/enable - Enable signups
router.post('/signups/enable', requireAdminAuth, async (req, res) => {
	signupsEnabled = true;
	await logAdminAction('enable_signups', 'admin', null, null);
	res.json({ enabled: true });
});

// POST /admin/signups/disable - Disable signups
router.post('/signups/disable', requireAdminAuth, async (req, res) => {
	signupsEnabled = false;
	await logAdminAction('disable_signups', 'admin', null, null);
	res.json({ enabled: false });
});

// GET /admin/users - List all users (show active status)
router.get('/users', requireAdminAuth, async (req, res) => {
	const users = await User.findAll({ attributes: ['id', 'homelab-user', 'role', 'active'] });
	res.json({ users });
});

// POST /admin/users - Create a new user
router.post('/users', requireAdminAuth, async (req, res) => {
	const { homelab-user, role, password } = req.body;
	if (!homelab-user || !password) return res.status(400).json({ error: 'Username and password required' });
	try {
		const user = await User.create({
			homelab-user,
			role: role || 'user',
			password: hashPassword(password),
		});
		await logAdminAction('create_user', 'admin', homelab-user, { role: user.role });
		res.status(201).json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role, active: user.active } });
	} catch (err) {
		res.status(400).json({ error: err.message });
	}
});

// POST /admin/users/:id/reset-password — set password (admin token auth)
router.post('/users/:id/reset-password', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const { password } = req.body;
	if (!password) return res.status(400).json({ error: 'Password required' });
	const user = await User.findByPk(id);
	if (!user) return res.status(404).json({ error: 'User not found' });
	user.password = hashPassword(password);
	await user.save();
	await logAdminAction('reset_user_password', 'admin', String(id), null);
	res.json({ message: 'Password reset' });
});

// PATCH /admin/users/:id/role — requires valid admin token (restrict in UI for superadmin)
router.patch('/users/:id/role', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const { role } = req.body;
	if (!role) return res.status(400).json({ error: 'Role required' });
	const user = await User.findByPk(id);
	if (!user) return res.status(404).json({ error: 'User not found' });
	user.role = role;
	await user.save();
	await logAdminAction('change_user_role', 'admin', String(id), { role });
	res.json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role, active: user.active } });
});

// PATCH /admin/users/:id/suspend - Suspend a user
router.patch('/users/:id/suspend', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const user = await User.findByPk(id);
	if (!user) return res.status(404).json({ error: 'User not found' });
	if (!user.active) return res.status(400).json({ error: 'User already suspended' });
	user.active = false;
	await user.save();
	await logAdminAction('suspend_user', 'admin', id, null);
	res.json({ message: `User ${id} suspended` });
});

// PATCH /admin/users/:id/activate - Activate a user
router.patch('/users/:id/activate', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const user = await User.findByPk(id);
	if (!user) return res.status(404).json({ error: 'User not found' });
	if (user.active) return res.status(400).json({ error: 'User already active' });
	user.active = true;
	await user.save();
	await logAdminAction('activate_user', 'admin', id, null);
	res.json({ message: `User ${id} activated` });
});

// DELETE /admin/users/:id - Delete a user
router.delete('/users/:id', requireAdminAuth, async (req, res) => {
	const id = parseInt(req.params.id, 10);
	const deleted = await User.destroy({ where: { id } });
	if (deleted) {
		await logAdminAction('delete_user', 'admin', id, null);
		res.json({ message: `User ${id} deleted` });
	} else {
		res.status(404).json({ error: 'User not found' });
	}
});

// GET /admin/polls - List all polls (show archived status)
router.get('/polls', requireAdminAuth, async (req, res) => {
	const rows = await Poll.findAll({ order: [['title', 'ASC']] });
	const polls = await Promise.all(rows.map((p) => toAdminPollShape(p)));
	res.json({ polls });
});

// POST /admin/polls - Create a new poll
router.post('/polls', requireAdminAuth, async (req, res) => {
	const { question, options } = req.body;
	if (!question || !Array.isArray(options) || options.length < 2) {
		return res.status(400).json({ error: 'Question and at least 2 options required' });
	}
	try {
		const poll = await Poll.create({
			id: randomId(16),
			title: question,
			options,
			expiration: 999999999999999,
			limit_ip: true,
			api_key: randomId(16),
			archived: false,
		});
		await logAdminAction('create_poll', 'admin', poll.id, { question });
		res.status(201).json({ poll: await toAdminPollShape(poll) });
	} catch (err) {
		res.status(400).json({ error: err.message });
	}
});

// GET /admin/polls/:id - Poll detail for admin UI
router.get('/polls/:id', requireAdminAuth, async (req, res) => {
	const poll = await Poll.findByPk(req.params.id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	res.json({ poll: await toAdminPollShape(poll) });
});

// PATCH /admin/polls/:id - Update question/options (clears votes when options change)
router.patch('/polls/:id', requireAdminAuth, async (req, res) => {
	const id = req.params.id;
	const { question, options } = req.body;
	if (!question || !Array.isArray(options) || options.length < 2) {
		return res.status(400).json({ error: 'Question and at least 2 options required' });
	}
	const poll = await Poll.findByPk(id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	const optsChanged = JSON.stringify(poll.options) !== JSON.stringify(options);
	poll.title = question;
	poll.options = options;
	await poll.save();
	if (optsChanged) await Vote.destroy({ where: { pollId: id } });
	await logAdminAction('update_poll', 'admin', id, null);
	res.json({ poll: await toAdminPollShape(poll) });
});

// PATCH /admin/polls/:id/archive - Archive a poll
router.patch('/polls/:id/archive', requireAdminAuth, async (req, res) => {
	const id = req.params.id;
	const poll = await Poll.findByPk(id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	if (poll.archived) return res.status(400).json({ error: 'Poll already archived' });
	poll.archived = true;
	await poll.save();
	await logAdminAction('archive_poll', 'admin', id, null);
	res.json({ message: `Poll ${id} archived` });
});

// PATCH /admin/polls/:id/unarchive - Unarchive a poll
router.patch('/polls/:id/unarchive', requireAdminAuth, async (req, res) => {
	const id = req.params.id;
	const poll = await Poll.findByPk(id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	if (!poll.archived) return res.status(400).json({ error: 'Poll is not archived' });
	poll.archived = false;
	await poll.save();
	await logAdminAction('unarchive_poll', 'admin', id, null);
	res.json({ message: `Poll ${id} unarchived` });
});

// DELETE /admin/polls/:id - Delete a poll
router.delete('/polls/:id', requireAdminAuth, async (req, res) => {
	const id = req.params.id;
	const poll = await Poll.findByPk(id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	await Vote.destroy({ where: { pollId: id } });
	await poll.destroy();
	await logAdminAction('delete_poll', 'admin', id, null);
	res.json({ message: `Poll ${id} deleted` });
});

// POST /admin/polls/:id/reset-votes - Reset poll votes (moderation)
router.post('/polls/:id/reset-votes', requireAdminAuth, async (req, res) => {
	const id = req.params.id;
	const poll = await Poll.findByPk(id);
	if (!poll) return res.status(404).json({ error: 'Poll not found' });
	await Vote.destroy({ where: { pollId: id } });
	await logAdminAction('reset_poll_votes', 'admin', id, null);
	res.json({ message: `Votes for poll ${id} reset` });
});

// GET /admin/audit-logs - List audit logs (filterable)
// Query params: action, actor, target, start, end, limit
router.get('/audit-logs', requireAdminAuth, async (req, res) => {
	const { action, actor, target, start, end, limit } = req.query;
	const where = {};
	if (action) where.action = action;
	if (actor) where.actor = actor;
	if (target) where.target = target;
	if (start || end) {
		where.createdAt = {};
		if (start) where.createdAt[Op.gte] = new Date(start);
		if (end) where.createdAt[Op.lte] = new Date(end);
	}
	const logs = await AuditLog.findAll({
		where,
		order: [['createdAt', 'DESC']],
		limit: limit ? parseInt(limit, 10) : 100
	});
	res.json({ logs });
});

module.exports = router;
