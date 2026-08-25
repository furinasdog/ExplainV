import { Router } from 'express';
import { v4 as uuid } from 'uuid';

import { authenticate } from '../middleware/auth.js';
import { readTasks, writeTasks } from './store.js';
import {
  scaleUpOne,
  scaleDownOne,
  waitForReady,
  findAvailablePod,
  createPodService,
  deletePodServiceByName,
} from '../services/cluster.js';

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
    podName: null,     // assigned Pod name
    serviceIP: null,   // per-pod Service external IP
    params: { problemText, problemImageBase64, refAudioBase64, quality, sections, briefSolution },
  };

  tasks.push(task);
  writeTasks(tasks);

  if (task.status === 'starting') {
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

// GET /api/tasks/:id
router.get('/:id', (req, res) => {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === req.params.id && t.username === req.user.username);
  if (!task) return res.status(404).json({ error: '任务不存在' });
  const { params, ...safeTask } = task;
  res.json(safeTask);
});

// DELETE /api/tasks/:id
router.delete('/:id', (req, res) => {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === req.params.id && t.username === req.user.username);
  if (!task) return res.status(404).json({ error: '任务不存在' });
  task.status = 'cancelled';
  task.updatedAt = new Date().toISOString();
  writeTasks(tasks);
  res.json({ status: 'cancelled' });
});

/**
 * Provision a Pod + Service, then submit the task directly to that Pod's IP.
 */
async function submitTask(taskId) {
  const tasks = readTasks();
  const task = tasks.find((t) => t.id === taskId);
  if (!task) return;

  // 1. Scale up StatefulSet
  console.log(`[${taskId}] Scaling up StatefulSet...`);
  const newCount = await scaleUpOne();

  // 2. Wait for the new Pod to be ready
  console.log(`[${taskId}] Waiting for ${newCount} Pod(s)...`);
  await waitForReady(newCount, 300_000);

  // 3. Find an available Pod (ready, not assigned to another task)
  const allTasksForExclude = readTasks();
  const usedPods = allTasksForExclude
    .filter((t) => t.status === 'running' || t.status === 'submitted' || t.status === 'queued')
    .map((t) => t.podName)
    .filter(Boolean);
  console.log(`[${taskId}] Finding available Pod...`);
  const podName = await findAvailablePod(usedPods);
  if (!podName) {
    throw new Error('No available Pod found');
  }
  console.log(`[${taskId}] Assigned Pod: ${podName}`);

  // 4. Get Pod cluster IP
  console.log(`[${taskId}] Getting IP for ${podName}...`);
  const serviceIP = await createPodService(podName);

  // 5. Record pod and service info in task
  const allTasks = readTasks();
  const t = allTasks.find((x) => x.id === taskId);
  if (t) {
    t.podName = podName;
    t.serviceIP = serviceIP;
    t.updatedAt = new Date().toISOString();
    writeTasks(allTasks);
  }

  // 6. Submit task directly to this Pod's Service IP
  const podUrl = `http://${serviceIP}:8000`;
  const { problemText, problemImageBase64, quality, sections, briefSolution } = task.params;

  console.log(`[${taskId}] Submitting to Pod ${podName} at ${podUrl}...`);

  const resp = await fetch(`${podUrl}/tasks`, {
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

  if (!resp.ok) {
    throw new Error(`Pod returned ${resp.status}: ${await resp.text()}`);
  }

  // 7. Mark task as running
  const finalTasks = readTasks();
  const ft = finalTasks.find((x) => x.id === taskId);
  if (ft) {
    ft.status = 'running';
    ft.stage = 'submitted';
    ft.updatedAt = new Date().toISOString();
    writeTasks(finalTasks);
  }

  console.log(`[${taskId}] Task submitted to ${podName} (${serviceIP})`);
}

export { scaleDownOne, deletePodServiceByName };
export default router;
