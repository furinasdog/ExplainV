import cron from 'node-cron';
import config from '../config.js';
import { readTasks, writeTasks } from '../routes/store.js';
import { scaleDownOne, scaleUpOne, waitForReady } from './cluster.js';

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
 * Poll the ExplainV API once, then match status to the correct task by task_id.
 */
async function pollAllTasks() {
  const tasks = readTasks();
  const running = tasks.filter((t) => t.status === 'running');
  if (running.length === 0) return;

  // Poll API /status once
  let status = null;
  try {
    const resp = await fetch(`${config.ackServiceUrl}/status`);
    if (resp.ok) {
      status = await resp.json();
    }
  } catch {
    console.log('[poller] API unreachable');
    return;
  }

  const allTasks = readTasks();

  if (!status.busy && !status.result && !status.error) {
    // API is idle with no result — all running tasks are stale
    console.log(`[poller] API idle, ${running.length} stale task(s) — marking failed`);
    for (const t of allTasks.filter((t) => t.status === 'running')) {
      t.status = 'failed';
      t.error = '任务进程丢失（Pod 可能已被回收）';
      t.updatedAt = new Date().toISOString();
    }
    writeTasks(allTasks);
    return;
  }

  // Match by task_id
  const apiTaskId = status.task_id;

  if (apiTaskId) {
    const matchedTask = allTasks.find((t) => t.id === apiTaskId && t.status === 'running');
    if (matchedTask) {
      matchedTask.progress = status.progress || 0;
      matchedTask.stage = status.stage || '';
      matchedTask.updatedAt = new Date().toISOString();

      if (!status.busy && status.result) {
        console.log(`[${apiTaskId}] Task completed!`);
        matchedTask.status = 'completed';
        matchedTask.progress = 1;
        matchedTask.stage = 'done';
        matchedTask.videoUrl = status.result.video_url;
        matchedTask.explanation = status.result.explanation;
        matchedTask.code = status.result.code;
        writeTasks(allTasks);
        await safeScaleDown(apiTaskId);
      } else if (!status.busy && status.error) {
        console.log(`[${apiTaskId}] Task failed: ${status.error}`);
        matchedTask.status = 'failed';
        matchedTask.error = status.error;
        writeTasks(allTasks);
        await safeScaleDown(apiTaskId);
      } else {
        writeTasks(allTasks);
        console.log(`[${apiTaskId}] ${(status.progress * 100).toFixed(0)}% (${status.stage})`);
      }
    } else {
      // task_id doesn't match any running task — might be stale
      console.log(`[poller] API task_id ${apiTaskId} not found in running tasks`);
      writeTasks(allTasks);
    }
  } else {
    // No task_id from API (old image?) — fallback: update oldest running task
    const oldest = allTasks
      .filter((t) => t.status === 'running')
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt))[0];

    if (oldest) {
      oldest.progress = status.progress || 0;
      oldest.stage = status.stage || '';
      oldest.updatedAt = new Date().toISOString();

      if (!status.busy && status.result) {
        oldest.status = 'completed';
        oldest.progress = 1;
        oldest.stage = 'done';
        oldest.videoUrl = status.result.video_url;
        oldest.explanation = status.result.explanation;
        oldest.code = status.result.code;
        writeTasks(allTasks);
        await safeScaleDown(oldest.id);
      } else if (!status.busy && status.error) {
        oldest.status = 'failed';
        oldest.error = status.error;
        writeTasks(allTasks);
        await safeScaleDown(oldest.id);
      } else {
        writeTasks(allTasks);
      }
    }
  }
}

async function safeScaleDown(taskId) {
  try {
    console.log(`[${taskId}] Scaling down Pod...`);
    await scaleDownOne();
  } catch (err) {
    console.error(`[${taskId}] Scale down failed:`, err);
  }
}

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
    await scaleUpOne();
    const newCount = running.length + 1;
    await waitForReady(newCount, 300_000);

    const { problemText, problemImageBase64, quality, sections, briefSolution } = nextTask.params;

    for (let attempt = 1; attempt <= 5; attempt++) {
      const resp = await fetch(`${config.ackServiceUrl}/tasks`, {
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

      if (resp.ok) {
        const allTasks = readTasks();
        const t = allTasks.find((x) => x.id === nextTask.id);
        if (t) {
          t.status = 'running';
          t.stage = 'submitted';
          t.updatedAt = new Date().toISOString();
          writeTasks(allTasks);
        }
        console.log(`[queue] Task ${nextTask.id} started`);
        return;
      }

      if (resp.status === 503 && attempt < 5) {
        await new Promise((r) => setTimeout(r, 10_000));
      } else {
        throw new Error(`API returned ${resp.status}`);
      }
    }
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
