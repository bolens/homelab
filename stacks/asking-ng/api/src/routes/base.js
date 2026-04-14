const express = require('express');
const router = express.Router();
const User = require('../models/user.sequelize');
const { hashPassword, comparePassword, generateToken, verifyToken } = require('../utils/auth');
// JWT authentication middleware
function requireAuth(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (!authHeader) return res.status(401).json({ error: 'Missing Authorization header' });
  const token = authHeader.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Missing token' });
  const payload = verifyToken(token);
  if (!payload) return res.status(401).json({ error: 'Invalid or expired token' });
  req.user = payload;
  next();
}
// GET /profile - Get current user's profile (protected)
router.get('/profile', requireAuth, async (req, res) => {
  const user = await User.findByPk(req.user.id, { attributes: ['id', 'homelab-user', 'role'] });
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json({ user });
});

// PUT /profile - Update current user's profile (protected)
router.put('/profile', requireAuth, async (req, res) => {
  const user = await User.findByPk(req.user.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  const { homelab-user, password } = req.body;
  if (homelab-user) user.homelab-user = homelab-user;
  if (password) user.password = hashPassword(password);
  await user.save();
  res.json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role } });
});

// healthcheck route (main API health)
router.get('/healthcheck', (req, res) => {
  res.status(200).json({ status: 'ok', message: 'API is healthy' });
});

// GET /users - List all users (protected)
router.get('/users', requireAuth, async (req, res) => {
  const users = await User.findAll({ attributes: ['id', 'homelab-user', 'role'] });
  res.json({ users });
});

// GET /users/:id - Get user by id (protected)
router.get('/users/:id', requireAuth, async (req, res) => {
  const id = parseInt(req.params.id, 10);
  const user = await User.findByPk(id, { attributes: ['id', 'homelab-user', 'role'] });
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json(user);
});

// POST /users - Create user (protected, admin only)
router.post('/users', requireAuth, async (req, res) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin only' });
  const { homelab-user, role, password } = req.body;
  if (!homelab-user || !password) return res.status(400).json({ error: 'Username and password required' });
  try {
    const user = await User.create({ homelab-user, password: hashPassword(password), role });
    res.status(201).json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role } });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// DELETE /users/:id - Delete user (protected, admin only)
router.delete('/users/:id', requireAuth, async (req, res) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin only' });
  const id = parseInt(req.params.id, 10);
  const deleted = await User.destroy({ where: { id } });
  if (deleted) {
    res.json({ message: `User ${id} deleted` });
  } else {
    res.status(404).json({ error: 'User not found' });
  }
});

// PATCH /users/:id/role - Update user role (protected, admin only)
router.patch('/users/:id/role', requireAuth, async (req, res) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin only' });
  const id = parseInt(req.params.id, 10);
  const { role } = req.body;
  if (!role) return res.status(400).json({ error: 'Role required' });
  const user = await User.findByPk(id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  user.role = role;
  await user.save();
  res.json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role } });
});

// POST /users/:id/reset-password - Admin resets user password (protected, admin only)
router.post('/users/:id/reset-password', requireAuth, async (req, res) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin only' });
  const id = parseInt(req.params.id, 10);
  const { password } = req.body;
  if (!password) return res.status(400).json({ error: 'Password required' });
  const user = await User.findByPk(id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  user.password = hashPassword(password);
  await user.save();
  res.json({ message: 'Password reset' });
});

// POST /users/reset-password - User resets own password (protected)
router.post('/users/reset-password', requireAuth, async (req, res) => {
  const { oldPassword, newPassword } = req.body;
  if (!oldPassword || !newPassword) return res.status(400).json({ error: 'Old and new password required' });
  const user = await User.findByPk(req.user.id);
  if (!user || !comparePassword(oldPassword, user.password)) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  user.password = hashPassword(newPassword);
  await user.save();
  res.json({ message: 'Password updated' });
});

// POST /auth/register
router.post('/auth/register', async (req, res) => {
  const { homelab-user, password, role } = req.body;
  if (!homelab-user || !password) return res.status(400).json({ error: 'Username and password required' });
  try {
    const user = await User.create({ homelab-user, password: hashPassword(password), role });
    const token = generateToken(user);
    res.status(201).json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role }, token });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// POST /auth/login
router.post('/auth/login', async (req, res) => {
  const { homelab-user, password } = req.body;
  if (!homelab-user || !password) return res.status(400).json({ error: 'Username and password required' });
  const user = await User.findOne({ where: { homelab-user } });
  if (!user || !comparePassword(password, user.password)) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  const token = generateToken(user);
  res.json({ user: { id: user.id, homelab-user: user.homelab-user, role: user.role }, token });
});

module.exports = router;
