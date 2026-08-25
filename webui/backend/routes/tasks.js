import { Router } from 'express';
import { v4 as uuid } from 'uuid';

import { authenticate } from '../middleware/auth.js';
import { readTasks, writeTasks } from './store.js';
import { scaleUpOne, scaleDownOne, waitForReady, getReplicaCount } from '../services/cluster.js';
import config from '../config.js';

const router = Router();

router.use(authenticate);

// POST /api/tasks — create a new video generation task
router.post('/', async (req, res) => {
  const { problemText, problemImageBase64, refAudioBase64, quality, sections, briefSolution } = req.body;

  if (!problemText && !problemImageBase64) {
    return res.status(400).json({ error: '必须提供题目文本或题目图片' });
  }

  const tasks = readTasks();
  const taskId = uuid();
  const now = new Date().toISOString();

  // Count running tasks to check capacity
  const runningCount = tasks.filter((t) => t.status === 'running' || t.status === 'starting').length;
  const queuedCount = tasks.filter((t) => t.status === 'queued').length;

  const task = {
    id: taskId,
    username: req.user.username,
    status: runningCount >= 10 ? 'queued' : 'starting',
    progress: 0,
    stage: runningCount >= 10 ? 'queued' : 'scaling_up',
    videoUrl: null,
    explanation: null,
    code: null,
    error: null,
    createdAt: now,
    updatedAt: now,
    params: { problemText, problemImageBase64, refAudioBase64, quality, sections, briefSolution },
  };

  tasks.push(task);
  writeTasks(tasks);

  if (task.status === 'starting') {
    // Start immediately in background
    submitTask(taskId).catch((err) => {
      console.error(`Task ${taskId} failed:`, err);
      const allTasks = readTasks();
      const t = allTasks.find((x) => x.id === taskId);
      if (t) {
        t.status = 'failed';
        t.error = `任务提交失败: ${err.message}`;
        t.updatedAt = new Date().toISOString();
        writeTasks(allTasks);
      }
    });
  }

  res.status(202).json({
    taskId,
    status: task.status,
    queuePosition: task.status === 'queued' ? queuedCount + 1 : 0,
  });
});

// GET /api/tasks — list current user's tasks
router.get('/', (_req, res) => {
  const tasks = readTasks()
    .filter((t) => t.username === _req.user.username)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(({ params, ...rest }) => rest);

  res.json(tasks);
});

// GET /api/tasks/:id — get task detail
router.get('/:id', (req, res) => {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === req.params.id && t.username === req.user.username);
  if (!task) {
    return res.status(404).json({ error: '任务不存在' });
  }

  const { params, ...safeTask } = task;
  res.json(safeTask);
});

// DELETE /api/tasks/:id — cancel task
router.delete('/:id', (req, res) => {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === req.params.id && t.username === req.user.username);
  if (!task) {
    return res.status(404).json({ error: '任务不存在' });
  }

  task.status = 'cancelled';
  task.updatedAt = new Date().toISOString();
  writeTasks(tasks);

  res.json({ status: 'cancelled' });
});

/**
 * Scale up a Pod and submit the task to ExplainV API.
 * Retries submission if a busy Pod responds with 503.
 */
async function submitTask(taskId) {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === taskId);
  if (!task) return;

  // 1. Scale up by 1 Pod
  console.log(`[${taskId}] Scaling up a new Pod...`);
  const newCount = await scaleUpOne();

  // 2. Wait for the new Pod count to be ready
  console.log(`[${taskId}] Waiting for ${newCount} Pod(s) to be ready...`);
  await waitForReady(newCount, 300_000);

  // 3. Submit task to ExplainV API (retry up to 5 times if 503)
  const { problemText, problemImageBase64, quality, sections, briefSolution } = task.params;

  for (let attempt = 1; attempt <= 5; attempt++) {
    console.log(`[${taskId}] Submitting to API (attempt ${attempt})...`);

    const resp = await fetch(`${config.ackServiceUrl}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        problem_text: problemText,
        problem_image_base64: problemImageBase64,
        quality: quality || 'l',
        sections: sections || null,
        brief_solution: briefSolution || false,
        task_id: taskId,
      }),
    });

    if (resp.ok) {
      // Update status
      const allTasks = readTasks();
      const t = allTasks.find((x) => x.id === taskId);
      if (t) {
        t.status = 'running';
        t.stage = 'submitted';
        t.updatedAt = new Date().toISOString();
        writeTasks(allTasks);
      }
      console.log(`[${taskId}] Task submitted successfully`);
      return;
    }

    if (resp.status === 503 && attempt < 5) {
      // Hit a busy Pod, wait and retry (LB might route to a free Pod next time)
      console.log(`[${taskId}] Pod busy (503), retrying in 10s...`);
      await new Promise((r) => setTimeout(r, 10_000));
    } else {
      throw new Error(`ExplainV API returned ${resp.status}: ${await resp.text()}`);
    }
  }
}

export { scaleDownOne };
export default router;
