import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import {
  listPods,
  deletePod,
  getReplicaCount,
  setReplicas,
  getPodServiceMap,
  getPodLogs,
} from '../services/cluster.js';
import { readTasks, writeTasks } from './store.js';

const router = Router();

function requireAdmin(req, res, next) {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: '需要管理员权限' });
  }
  next();
}

router.use(authenticate, requireAdmin);

// GET /api/admin/pods
router.get('/pods', async (_req, res) => {
  try {
    const pods = await listPods();
    const serviceMap = await getPodServiceMap();
    const replicaCount = await getReplicaCount();
    const tasks = readTasks().filter((t) => t.status === 'running' || t.status === 'starting');

    // Merge service info into pod data
    const podsWithServices = pods.map((pod) => {
      const svc = serviceMap.find((s) => s.podName === pod.name);
      return {
        ...pod,
        serviceIP: svc?.externalIP || null,
      };
    });

    res.json({
      desiredReplicas: replicaCount,
      pods: podsWithServices,
      runningTasks: tasks.map(({ params, ...rest }) => rest),
    });
  } catch (err) {
    res.status(500).json({ error: `获取 Pod 列表失败: ${err.message}` });
  }
});

// GET /api/admin/pods/:name/logs — get Pod logs
router.get('/pods/:name/logs', async (req, res) => {
  const podName = req.params.name;
  const tailLines = parseInt(req.query.tailLines) || 500;
  const sinceSeconds = parseInt(req.query.sinceSeconds) || 3600;

  try {
    const logs = await getPodLogs(podName, { tailLines, sinceSeconds });
    res.json({ podName, logs });
  } catch (err) {
    res.status(500).json({ error: `获取 Pod 日志失败: ${err.message}` });
  }
});

// DELETE /api/admin/pods/:name
router.delete('/pods/:name', async (req, res) => {
  const podName = req.params.name;

  try {
    // Delete Pod and its Service
    await deletePod(podName);

    // Scale down StatefulSet by 1
    const current = await getReplicaCount();
    if (current > 0) {
      await setReplicas(current - 1);
    }

    // Mark running tasks on this Pod as failed
    const tasks = readTasks();
    const affected = tasks.filter(
      (t) => (t.status === 'running' || t.status === 'starting') && t.podName === podName
    );
    for (const t of affected) {
      t.status = 'failed';
      t.error = `Pod 被管理员强制删除 (${podName})`;
      t.updatedAt = new Date().toISOString();
    }
    writeTasks(tasks);

    res.json({
      message: `Pod ${podName} 已删除，${affected.length} 个任务已标记为失败`,
      cancelledTasks: affected.map((t) => t.id),
    });
  } catch (err) {
    res.status(500).json({ error: `删除 Pod 失败: ${err.message}` });
  }
});

// PUT /api/admin/pods/scale
router.put('/pods/scale', async (req, res) => {
  const { replicas } = req.body;
  if (replicas === undefined || replicas < 0) {
    return res.status(400).json({ error: 'replicas 必须是非负整数' });
  }

  try {
    const newCount = await setReplicas(replicas);

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

// POST /api/admin/tasks/cleanup
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

// GET /api/admin/tasks
router.get('/tasks', (_req, res) => {
  const tasks = readTasks()
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(({ params, ...rest }) => rest);
  res.json(tasks);
});

export default router;
