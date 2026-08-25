import * as k8s from '@kubernetes/client-node';
import { existsSync } from 'fs';
import config from '../config.js';

const MAX_PODS = 20;

let kc = null;
let appsApi = null;
let coreApi = null;

function getClient() {
  if (kc) return { kc, appsApi, coreApi };
  kc = new k8s.KubeConfig();

  // In-cluster: use ServiceAccount token; fallback: load from kubeconfig file
  if (existsSync('/var/run/secrets/kubernetes.io/serviceaccount/token')) {
    kc.loadFromCluster();
    console.log('Using in-cluster K8s authentication');
  } else {
    kc.loadFromFile(config.kubeconfigPath);
    console.log(`Using kubeconfig: ${config.kubeconfigPath}`);
  }

  appsApi = kc.makeApiClient(k8s.AppsV1Api);
  coreApi = kc.makeApiClient(k8s.CoreV1Api);
  return { kc, appsApi, coreApi };
}

// ---------------------------------------------------------------------------
// StatefulSet management
// ---------------------------------------------------------------------------

export async function getReplicaCount() {
  const { appsApi } = getClient();
  const resp = await appsApi.readNamespacedStatefulSet({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
  });
  const ss = resp.body || resp;
  return ss.spec.replicas || 0;
}

export async function setReplicas(replicas) {
  const { appsApi } = getClient();
  const capped = Math.min(Math.max(0, replicas), MAX_PODS);

  const resp = await appsApi.readNamespacedStatefulSet({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
  });
  const ss = resp.body || resp;
  ss.spec.replicas = capped;

  await appsApi.replaceNamespacedStatefulSet({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
    body: ss,
  });

  console.log(`Scaled StatefulSet to ${capped} replica(s)`);
  return capped;
}

export async function scaleUpOne() {
  const current = await getReplicaCount();
  if (current >= MAX_PODS) {
    throw new Error(`已达到最大 Pod 数量 (${MAX_PODS})`);
  }
  return await setReplicas(current + 1);
}

export async function scaleDownOne() {
  const current = await getReplicaCount();
  if (current > 0) {
    await setReplicas(current - 1);
  }
}

// ---------------------------------------------------------------------------
// Pod management
// ---------------------------------------------------------------------------

export async function listPods() {
  const { coreApi } = getClient();
  const resp = await coreApi.listNamespacedPod({
    namespace: config.ackNamespace,
    labelSelector: `app=${config.ackDeployment}`,
  });
  const podList = resp.body || resp;
  return (podList.items || []).map((pod) => ({
    name: pod.metadata.name,
    status: pod.status?.phase || 'Unknown',
    ready: (pod.status?.conditions || []).some(
      (c) => c.type === 'Ready' && c.status === 'True'
    ),
    podIP: pod.status?.podIP || null,
    createdAt: pod.metadata.creationTimestamp,
    node: pod.spec?.nodeName || 'N/A',
  }));
}

/**
 * Wait until at least `count` Pods are Ready.
 */
export async function waitForReady(count = 1, timeoutMs = 300_000) {
  const { coreApi } = getClient();
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await coreApi.listNamespacedPod({
        namespace: config.ackNamespace,
        labelSelector: `app=${config.ackDeployment}`,
      });
      const podList = resp.body || resp;
      const readyCount = (podList.items || []).filter((pod) =>
        (pod.status?.conditions || []).some(
          (c) => c.type === 'Ready' && c.status === 'True'
        )
      ).length;

      if (readyCount >= count) {
        console.log(`${readyCount} Pod(s) ready`);
        return;
      }
    } catch { /* keep waiting */ }

    await new Promise((r) => setTimeout(r, 5000));
  }

  throw new Error(`Pods not ready after ${timeoutMs / 1000}s`);
}

/**
 * Find a ready Pod that is not already assigned to a running task.
 * @param {string[]} [excludePods] - Pod names to exclude (already in use).
 * Returns the pod name (e.g. "explainv-api-0") or null.
 */
export async function findAvailablePod(excludePods = []) {
  const pods = await listPods();
  const usedPods = new Set(excludePods);

  const available = pods.find(
    (p) => p.ready && !usedPods.has(p.name)
  );

  return available ? available.name : null;
}

// ---------------------------------------------------------------------------
// Pod IP direct access (in-cluster, no LoadBalancer needed)
// ---------------------------------------------------------------------------

/**
 * Get the cluster IP for a Pod. Returns the pod's IP directly.
 */
export async function createPodService(podName) {
  const pods = await listPods();
  const pod = pods.find((p) => p.name === podName);

  if (!pod) throw new Error(`Pod ${podName} not found`);
  if (!pod.podIP) throw new Error(`Pod ${podName} has no IP yet`);

  console.log(`Using Pod ${podName} cluster IP: ${pod.podIP}`);
  return pod.podIP;
}

/**
 * No-op: no services to clean up when using direct pod IP.
 */
export async function deletePodService(_svcName) {}
export async function deletePodServiceByName(_podName) {}

/**
 * Get all pod service mappings: [{ podName, externalIP }].
 */
export async function getPodServiceMap() {
  const pods = await listPods();
  return pods
    .filter((p) => p.ready && p.podIP)
    .map((p) => ({ podName: p.name, externalIP: p.podIP }));
}

// ---------------------------------------------------------------------------
// Pod deletion (admin)
// ---------------------------------------------------------------------------

export async function deletePod(podName) {
  const { coreApi } = getClient();
  await coreApi.deleteNamespacedPod({
    name: podName,
    namespace: config.ackNamespace,
    body: {
      apiVersion: 'v1',
      kind: 'DeleteOptions',
      gracePeriodSeconds: 0,
    },
  });
  console.log(`Force deleted Pod: ${podName}`);

  // Also delete the associated Service
  await deletePodServiceByName(podName).catch(() => {});
}

// ---------------------------------------------------------------------------
// Pod logs (admin)
// ---------------------------------------------------------------------------

/**
 * Get logs from a specific Pod.
 * @param {string} podName - Pod name
 * @param {object} [options] - { container, tailLines, sinceSeconds }
 * @returns {string} log text
 */
export async function getPodLogs(podName, options = {}) {
  const { coreApi } = getClient();
  const { tailLines = 500, sinceSeconds = 3600 } = options;

  const resp = await coreApi.readNamespacedPodLog({
    name: podName,
    namespace: config.ackNamespace,
    tailLines,
    sinceSeconds,
    timestamps: true,
  });

  return resp.body || resp || '';
}

// ---------------------------------------------------------------------------
// Health check helper
// ---------------------------------------------------------------------------

/**
 * Poll the health endpoint until it responds with 200.
 */
async function waitForHealth(ip, port, timeoutMs) {
  const start = Date.now();
  const url = `http://${ip}:${port}/health`;

  while (Date.now() - start < timeoutMs) {
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (resp.ok) {
        console.log(`Health check passed for ${ip}:${port}`);
        return true;
      }
    } catch { /* not ready yet */ }
    await new Promise((r) => setTimeout(r, 3000));
  }
  return false;
}
