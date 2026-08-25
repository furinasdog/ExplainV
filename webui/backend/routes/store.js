import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve } from 'path';
import config from '../config.js';

const TASKS_FILE = resolve(config.dataDir, 'tasks.json');

export function readTasks() {
  if (!existsSync(TASKS_FILE)) return [];
  try {
    return JSON.parse(readFileSync(TASKS_FILE, 'utf-8'));
  } catch {
    return [];
  }
}

export function writeTasks(tasks) {
  writeFileSync(TASKS_FILE, JSON.stringify(tasks, null, 2), 'utf-8');
}
