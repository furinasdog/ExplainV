import cron from 'node-cron';
import { readTasks, writeTasks } from '../routes/store.js';
import { scaleDownOne, scaleUpOne, waitForReady, createPodService, findAvailablePod, deletePodServiceByName } from './cluster.js';

let polling = false;

export function startPoller() {
  console.log('Task poller started (every 60 seconds)');

  cron.schedule('* * * * *', async () => {
    if (polling) return;
    polling = true;

    try {
      await pollAllTasks();
      await processQueuedTasks();
    } catch (err) {
      console.error('Poller error:', err);
    } finally {
      polling = false;
    }
  });
}

/**
 * Poll each running task directly via its assigned Pod's Service IP.
 * No LoadBalancer ambiguity — each task has its own dedicated IP.
 */
async function pollAllTasks() {
  const tasks = readTasks();
  const running = tasks.filter((t) => t.status === 'running');
  if (running.length === 0) return;

  for (const task of running) {
    try {
      await pollTask(task);
    } catch (err) {
      console.error(`Poll task ${task.id} error:`, err);
    }
  }
}

async function pollTask(task) {
  if (!task.serviceIP) {
    console.log(`[${task.id}] No serviceIP assigned yet, skipping`);
    return;
  }

  const podUrl = `http://${task.serviceIP}:8000`;

  let status;
  try {
    const resp = await fetch(`${podUrl}/status`, { signal: AbortSignal.timeout(10000) });
    if (!resp.ok) return;
    status = await resp.json();
  } catch (err) {
    // Pod unreachable — might have been deleted
    console.log(`[${task.id}] Pod ${task.podName} unreachable (${err.message})`);
    const allTasks = readTasks();
    const t = allTasks.find((x) => x.id === task.id);
    if (t && t.status === 'running') {
      t.status = 'failed';
      t.error = 'Pod 不可达（可能已被回收）';
      t.updatedAt = new Date().toISOString();
      writeTasks(allTasks);
      await cleanupPod(task);
    }
    return;
  }

  const allTasks = readTasks();
  const t = allTasks.find((x) => x.id === task.id);
  if (!t || t.status !== 'running') return;

  t.progress = status.progress || 0;
  t.stage = status.stage || '';
  t.updatedAt = new Date().toISOString();

  if (!status.busy && status.result) {
    console.log(`[${task.id}] Completed on ${task.podName}!`);
    t.status = 'completed';
    t.progress = 1;
    t.stage = 'done';
    t.videoUrl = status.result.video_url;
    t.explanation = status.result.explanation;
    t.code = status.result.code;
    writeTasks(allTasks);
    await cleanupPod(task);
  } else if (!status.busy && status.error) {
    console.log(`[${task.id}] Failed on ${task.podName}: ${status.error}`);
    t.status = 'failed';
    t.error = status.error;
    writeTasks(allTasks);
    await cleanupPod(task);
  } else {
    writeTasks(allTasks);
    console.log(`[${task.id}] ${(status.progress * 100).toFixed(0)}% (${status.stage}) on ${task.podName}`);
  }
}

/**
 * Clean up after a task finishes: scale down + delete per-pod Service.
 */
async function cleanupPod(task) {
  try {
    if (task.podName) {
      console.log(`[${task.id}] Cleaning up Pod ${task.podName}...`);
      await deletePodServiceByName(task.podName);
    }
    await scaleDownOne();
  } catch (err) {
    console.error(`[${task.id}] Cleanup failed:`, err);
  }
}

/**
 * Process queued tasks when capacity is available.
 */
async function processQueuedTasks() {
  const tasks = readTasks();
  const running = tasks.filter((t) => t.status === 'running' || t.status === 'starting');
  const queued = tasks.filter((t) => t.status === 'queued')
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  if (queued.length === 0 || running.length >= 10) return;

  const nextTask = queued[0];
  console.log(`[queue] Starting queued task ${nextTask.id}...`);

  nextTask.status = 'starting';
  nextTask.stage = 'scaling_up';
  nextTask.updatedAt = new Date().toISOString();
  writeTasks(tasks);

  try {
    // Scale up
    const newCount = await scaleUpOne();
    await waitForReady(newCount, 300_000);

    // Find available Pod (exclude those already assigned to running tasks)
    const tasksForExclude = readTasks();
    const usedPods = tasksForExclude
      .filter((t) => t.status === 'running' || t.status === 'submitted' || t.status === 'queued')
      .map((t) => t.podName)
      .filter(Boolean);
    const podName = await findAvailablePod(usedPods);
    if (!podName) throw new Error('No available Pod');

    const podAddr = await createPodService(podName);

    // Update task with pod info
    const allTasks = readTasks();
    const t = allTasks.find((x) => x.id === nextTask.id);
    if (t) {
      t.podName = podName;
      t.serviceIP = podAddr;
    }

    // Submit directly to this Pod via shared LB
    const podUrl = `http://${podAddr}:8000`;
    const { problemText, problemImageBase64, quality, sections, briefSolution } = nextTask.params;

    console.log(`[queue] Submitting ${nextTask.id} to ${podName} (${podAddr})...`);

    const resp = await fetch(`${podUrl}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        problem_text: problemText,
        problem_image_base64: problemImageBase64,
        quality: quality || 'l',
        sections: sections || null,
        brief_solution: briefSolution || false,
        task_id: nextTask.id,
      }),
    });

    if (!resp.ok) throw new Error(`Pod returned ${resp.status}`);

    const finalTasks = readTasks();
    const ft = finalTasks.find((x) => x.id === nextTask.id);
    if (ft) {
      ft.status = 'running';
      ft.stage = 'submitted';
      ft.updatedAt = new Date().toISOString();
      writeTasks(finalTasks);
    }
    console.log(`[queue] Task ${nextTask.id} started on ${podName}`);
  } catch (err) {
    console.error(`[queue] Failed to start ${nextTask.id}:`, err);
    const allTasks = readTasks();
    const t = allTasks.find((x) => x.id === nextTask.id);
    if (t) {
      t.status = 'failed';
      t.error = `排队任务启动失败: ${err.message}`;
      t.updatedAt = new Date().toISOString();
      writeTasks(allTasks);
    }
  }
}
