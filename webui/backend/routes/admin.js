import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import { listPods, deletePod, getReplicaCount, setReplicas } from '../services/cluster.js';
import { readTasks, writeTasks } from './store.js';

const router = Router();

function requireAdmin(req, res, next) {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: '需要管理员权限' });
  }
  next();
}

router.use(authenticate, requireAdmin);

// GET /api/admin/pods — list all ExplainV API Pods
router.get('/pods', async (_req, res) => {
  try {
    const pods = await listPods();
    const replicaCount = await getReplicaCount();
    const tasks = readTasks().filter((t) => t.status === 'running' || t.status === 'starting');

    res.json({
      desiredReplicas: replicaCount,
      pods,
      runningTasks: tasks.map(({ params, ...rest }) => rest),
    });
  } catch (err) {
    res.status(500).json({ error: `获取 Pod 列表失败: ${err.message}` });
  }
});

// DELETE /api/admin/pods/:name — force delete a Pod + cancel running tasks
router.delete('/pods/:name', async (req, res) => {
  const podName = req.params.name;

  try {
    // 1. Delete the Pod
    await deletePod(podName);

    // 2. Scale down by 1 (otherwise deployment recreates the Pod)
    const current = await getReplicaCount();
    if (current > 0) {
      await setReplicas(current - 1);
    }

    // 3. Mark running tasks as failed
    const tasks = readTasks();
    const running = tasks.filter((t) => t.status === 'running' || t.status === 'starting');
    for (const t of running) {
      t.status = 'failed';
      t.error = `Pod 被管理员强制删除 (${podName})`;
      t.updatedAt = new Date().toISOString();
    }
    writeTasks(tasks);

    res.json({
      message: `Pod ${podName} 已删除，${running.length} 个任务已标记为失败`,
      cancelledTasks: running.map((t) => t.id),
    });
  } catch (err) {
    res.status(500).json({ error: `删除 Pod 失败: ${err.message}` });
  }
});

// PUT /api/admin/pods/scale — manually set replica count
router.put('/pods/scale', async (req, res) => {
  const { replicas } = req.body;
  if (replicas === undefined || replicas < 0) {
    return res.status(400).json({ error: 'replicas 必须是非负整数' });
  }

  try {
    const newCount = await setReplicas(replicas);

    // If scaling down to 0, cancel all running tasks
    if (newCount === 0) {
      const tasks = readTasks();
      const running = tasks.filter((t) => t.status === 'running' || t.status === 'starting');
      for (const t of running) {
        t.status = 'failed';
        t.error = 'Pod 被管理员缩容至 0';
        t.updatedAt = new Date().toISOString();
      }
      writeTasks(tasks);
    }

    res.json({ replicas: newCount });
  } catch (err) {
    res.status(500).json({ error: `扩缩容失败: ${err.message}` });
  }
});

// POST /api/admin/tasks/cleanup — cancel all stuck running/starting tasks
router.post('/tasks/cleanup', (_req, res) => {
  const tasks = readTasks();
  let count = 0;

  for (const t of tasks) {
    if (t.status === 'running' || t.status === 'starting') {
      t.status = 'failed';
      t.error = '管理员手动清理';
      t.updatedAt = new Date().toISOString();
      count++;
    }
  }

  writeTasks(tasks);
  res.json({ message: `已清理 ${count} 个卡住的任务` });
});

// GET /api/admin/tasks — list all tasks (all users)
router.get('/tasks', (_req, res) => {
  const tasks = readTasks()
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(({ params, ...rest }) => rest);
  res.json(tasks);
});

export default router;
