import express from 'express';
import cors from 'cors';
import { mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

import config from './config.js';
import authRoutes from './routes/auth.js';
import taskRoutes from './routes/tasks.js';
import adminRoutes from './routes/admin.js';
import { startPoller } from './services/poller.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Ensure data directories exist
mkdirSync(config.dataDir, { recursive: true });
mkdirSync(config.uploadDir, { recursive: true });

const app = express();

app.use(cors());
app.use(express.json({ limit: '50mb' })); // base64 images can be large

// Serve Vue frontend in production
const frontendDist = resolve(__dirname, '../frontend/dist');
app.use(express.static(frontendDist));

// API routes
app.use('/api/auth', authRoutes);
app.use('/api/tasks', taskRoutes);
app.use('/api/admin', adminRoutes);

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// SPA fallback — serve index.html for non-API routes
app.get('*', (_req, res) => {
  res.sendFile(resolve(frontendDist, 'index.html'));
});

// Start server
app.listen(config.port, '0.0.0.0', () => {
  console.log(`ExplainV backend running on http://0.0.0.0:${config.port}`);
  startPoller();
});
