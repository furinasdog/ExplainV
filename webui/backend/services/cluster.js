import * as k8s from '@kubernetes/client-node';
import config from '../config.js';

const MAX_PODS = 10;

let kc = null;
let appsApi = null;
let coreApi = null;

function getClient() {
  if (kc) return { kc, appsApi, coreApi };

  kc = new k8s.KubeConfig();
  kc.loadFromFile(config.kubeconfigPath);

  appsApi = kc.makeApiClient(k8s.AppsV1Api);
  coreApi = kc.makeApiClient(k8s.CoreV1Api);

  return { kc, appsApi, coreApi };
}

/**
 * Get the current replica count of the deployment.
 */
export async function getReplicaCount() {
  const { appsApi } = getClient();
  const response = await appsApi.readNamespacedDeployment({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
  });
  const deployment = response.body || response;
  return deployment.spec.replicas || 0;
}

/**
 * Scale the deployment to the given number of replicas.
 */
export async function setReplicas(replicas) {
  const { appsApi } = getClient();
  const capped = Math.min(Math.max(0, replicas), MAX_PODS);

  const response = await appsApi.readNamespacedDeployment({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
  });
  const deployment = response.body || response;
  deployment.spec.replicas = capped;

  await appsApi.replaceNamespacedDeployment({
    name: config.ackDeployment,
    namespace: config.ackNamespace,
    body: deployment,
  });

  console.log(`Scaled ${config.ackDeployment} to ${capped} replica(s)`);
  return capped;
}

/**
 * Scale up by 1 (for a new task). Returns the new replica count.
 * Capped at MAX_PODS.
 */
export async function scaleUpOne() {
  const current = await getReplicaCount();
  if (current >= MAX_PODS) {
    throw new Error(`已达到最大 Pod 数量 (${MAX_PODS})，请排队等待`);
  }
  return await setReplicas(current + 1);
}

/**
 * Scale down by 1 (after task completes).
 */
export async function scaleDownOne() {
  const current = await getReplicaCount();
  if (current > 0) {
    await setReplicas(current - 1);
  }
}

/**
 * Wait until at least `count` Pods are Ready.
 * Polls every 5 seconds, times out after `timeoutMs`.
 */
export async function waitForReady(count = 1, timeoutMs = 300_000) {
  const { coreApi } = getClient();
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    try {
      const response = await coreApi.listNamespacedPod({
        namespace: config.ackNamespace,
        labelSelector: `app=${config.ackDeployment}`,
      });

      const podList = response.body || response;
      const items = podList.items || [];

      const readyCount = items.filter((pod) => {
        const conditions = pod.status?.conditions || [];
        return conditions.some(
          (c) => c.type === 'Ready' && c.status === 'True'
        );
      }).length;

      if (readyCount >= count) {
        console.log(`${readyCount} Pod(s) ready`);
        return;
      }
    } catch {
      // keep waiting
    }

    await new Promise((r) => setTimeout(r, 5000));
  }

  throw new Error(`Pods not ready after ${timeoutMs / 1000}s`);
}

/**
 * List all Pods of the ExplainV API deployment.
 */
export async function listPods() {
  const { coreApi } = getClient();
  const response = await coreApi.listNamespacedPod({
    namespace: config.ackNamespace,
    labelSelector: `app=${config.ackDeployment}`,
  });

  const podList = response.body || response;
  const items = podList.items || [];

  return items.map((pod) => ({
    name: pod.metadata.name,
    status: pod.status?.phase || 'Unknown',
    ready: (pod.status?.conditions || []).some(
      (c) => c.type === 'Ready' && c.status === 'True'
    ),
    createdAt: pod.metadata.creationTimestamp,
    node: pod.spec?.nodeName || 'N/A',
  }));
}

/**
 * Delete a specific Pod by name (force delete with grace period 0).
 */
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
}
