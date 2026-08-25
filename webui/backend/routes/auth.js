import { Router } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve } from 'path';

import config from '../config.js';
import { authenticate } from '../middleware/auth.js';

const router = Router();
const USERS_FILE = resolve(config.dataDir, 'users.json');
const DEVICES_FILE = resolve(config.dataDir, 'devices.json');

function readUsers() {
  if (!existsSync(USERS_FILE)) return {};
  try {
    return JSON.parse(readFileSync(USERS_FILE, 'utf-8'));
  } catch {
    return {};
  }
}

function writeUsers(users) {
  writeFileSync(USERS_FILE, JSON.stringify(users, null, 2), 'utf-8');
}

function readDevices() {
  if (!existsSync(DEVICES_FILE)) return {};
  try {
    return JSON.parse(readFileSync(DEVICES_FILE, 'utf-8'));
  } catch {
    return {};
  }
}

function writeDevices(devices) {
  writeFileSync(DEVICES_FILE, JSON.stringify(devices, null, 2), 'utf-8');
}

/**
 * Ensure default admin account exists on startup.
 */
async function ensureDefaultAdmin() {
  const users = readUsers();
  if (!users['Admin']) {
    const hash = await bcrypt.hash('Admin@321', 10);
    users['Admin'] = {
      hash,
      role: 'admin',
      createdAt: new Date().toISOString(),
      deviceFingerprint: 'system-default-admin',
    };
    writeUsers(users);
    console.log('Default admin account created (Admin / Admin@321)');
  } else if (!users['Admin'].role) {
    // Upgrade existing Admin to admin role
    users['Admin'].role = 'admin';
    writeUsers(users);
  }
}

// Run on module load
ensureDefaultAdmin();

// POST /api/auth/register
router.post('/register', async (req, res) => {
  const { username, password, deviceFingerprint } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: '用户名和密码不能为空' });
  }
  if (username.length < 2 || username.length > 32) {
    return res.status(400).json({ error: '用户名长度需在 2-32 个字符' });
  }
  if (password.length < 6) {
    return res.status(400).json({ error: '密码长度至少 6 个字符' });
  }

  // 设备指纹限制：每台设备只能创建一个账号
  if (deviceFingerprint) {
    const devices = readDevices();
    if (devices[deviceFingerprint]) {
      return res.status(409).json({ error: '该设备已注册过账号，每台设备仅允许注册一个账号' });
    }
  }

  const users = readUsers();
  if (users[username]) {
    return res.status(409).json({ error: '用户名已存在' });
  }

  const hash = await bcrypt.hash(password, 10);
  users[username] = {
    hash,
    role: 'user',
    createdAt: new Date().toISOString(),
    deviceFingerprint: deviceFingerprint || null,
  };
  writeUsers(users);

  // 记录设备指纹
  if (deviceFingerprint) {
    const devices = readDevices();
    devices[deviceFingerprint] = {
      username,
      registeredAt: new Date().toISOString(),
    };
    writeDevices(devices);
  }

  const token = jwt.sign({ username, role: 'user' }, config.jwtSecret, { expiresIn: '7d' });
  res.json({ token, username, role: 'user' });
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: '用户名和密码不能为空' });
  }

  const users = readUsers();
  const user = users[username];
  if (!user) {
    return res.status(401).json({ error: '用户名或密码错误' });
  }

  const valid = await bcrypt.compare(password, user.hash);
  if (!valid) {
    return res.status(401).json({ error: '用户名或密码错误' });
  }

  const role = user.role || 'user';
  const token = jwt.sign({ username, role }, config.jwtSecret, { expiresIn: '7d' });
  res.json({ token, username, role });
});

// GET /api/auth/me — get current user info
router.get('/me', authenticate, (req, res) => {
  const users = readUsers();
  const user = users[req.user.username];
  res.json({
    username: req.user.username,
    role: user?.role || req.user.role || 'user',
    createdAt: user?.createdAt || null,
  });
});

// ---------------------------------------------------------------------------
// Admin routes
// ---------------------------------------------------------------------------

function requireAdmin(req, res, next) {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: '需要管理员权限' });
  }
  next();
}

// GET /api/auth/admin/users — list all users (admin only)
router.get('/admin/users', authenticate, requireAdmin, (_req, res) => {
  const users = readUsers();
  const list = Object.entries(users).map(([username, data]) => ({
    username,
    role: data.role || 'user',
    createdAt: data.createdAt || null,
    deviceFingerprint: data.deviceFingerprint || null,
  }));
  res.json(list);
});

// POST /api/auth/admin/users — create user (admin only, bypasses device check)
router.post('/admin/users', authenticate, requireAdmin, async (req, res) => {
  const { username, password, role } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: '用户名和密码不能为空' });
  }

  const users = readUsers();
  if (users[username]) {
    return res.status(409).json({ error: '用户名已存在' });
  }

  const hash = await bcrypt.hash(password, 10);
  users[username] = {
    hash,
    role: role === 'admin' ? 'admin' : 'user',
    createdAt: new Date().toISOString(),
    deviceFingerprint: null,
  };
  writeUsers(users);

  res.json({ username, role: users[username].role });
});

// DELETE /api/auth/admin/users/:username — delete user (admin only)
router.delete('/admin/users/:username', authenticate, requireAdmin, (req, res) => {
  const { username } = req.params;

  if (username === req.user.username) {
    return res.status(400).json({ error: '不能删除自己的账户' });
  }

  const users = readUsers();
  if (!users[username]) {
    return res.status(404).json({ error: '用户不存在' });
  }

  // 同时清除设备指纹记录
  const fp = users[username].deviceFingerprint;
  if (fp) {
    const devices = readDevices();
    delete devices[fp];
    writeDevices(devices);
  }

  delete users[username];
  writeUsers(users);

  res.json({ message: '用户已删除' });
});

export default router;
