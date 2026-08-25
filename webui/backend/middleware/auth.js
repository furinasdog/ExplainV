import jwt from 'jsonwebtoken';
import config from '../config.js';

/**
 * JWT authentication middleware.
 * Extracts token from Authorization header and verifies it.
 * Sets req.user = { username } on success.
 */
export function authenticate(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: '未提供认证令牌' });
  }

  const token = header.slice(7);
  try {
    const payload = jwt.verify(token, config.jwtSecret);
    req.user = { username: payload.username, role: payload.role || 'user' };
    next();
  } catch {
    return res.status(401).json({ error: '认证令牌无效或已过期' });
  }
}
