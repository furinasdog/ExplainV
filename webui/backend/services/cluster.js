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
    throw new Error(`Max pods reached (${MAX_PODS})`);
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
 * Find a ready Pod that doesn't have a per-pod Service yet.
 * Returns the pod name (e.g. "explainv-api-0") or null.
 */
export async function findAvailablePod() {
  const pods = await listPods();
  const existingServices = await listPodServices();
  const usedPods = new Set(existingServices.map((s) => s.podName));

  const available = pods.find(
    (p) => p.ready && !usedPods.has(p.name)
  );

  return available ? available.name : null;
}

// ---------------------------------------------------------------------------
// Per-Pod LoadBalancer Service management
// ---------------------------------------------------------------------------

/**
 * List all per-pod LoadBalancer Services.
 */
export async function listPodServices() {
  const { coreApi } = getClient();
  const resp = await coreApi.listNamespacedService({
    namespace: config.ackNamespace,
    labelSelector: 'managed-by=explainv-webui',
  });
  const svcList = resp.body || resp;
  return (svcList.items || []).map((svc) => ({
    name: svc.metadata.name,
    podName: svc.metadata.labels['explainv-pod'],
    externalIP: svc.status?.loadBalancer?.ingress?.[0]?.ip || null,
  }));
}

/**
 * Create a LoadBalancer Service for a specific Pod and wait for its external IP.
 * Returns the external IP.
 */
export async function createPodService(podName) {
  const { coreApi } = getClient();
  const svcName = `svc-${podName}`;

  // Check if service already exists
  try {
    const existing = await coreApi.readNamespacedService({
      name: svcName,
      namespace: config.ackNamespace,
    });
    const ip = existing.body?.status?.loadBalancer?.ingress?.[0]?.ip
      || (existing.body || existing)?.status?.loadBalancer?.ingress?.[0]?.ip;
    if (ip) return ip;
  } catch { /* doesn't exist, create it */ }

  // Create LoadBalancer Service targeting this specific Pod
  await coreApi.createNamespacedService({
    namespace: config.ackNamespace,
    body: {
      apiVersion: 'v1',
      kind: 'Service',
      metadata: {
        name: svcName,
        labels: {
          'managed-by': 'explainv-webui',
          'explainv-pod': podName,
        },
      },
      spec: {
        type: 'LoadBalancer',
        selector: {
          'statefulset.kubernetes.io/pod-name': podName,
        },
        ports: [
          { port: 8000, targetPort: 8000, protocol: 'TCP' },
        ],
      },
    },
  });

  console.log(`Created Service ${svcName} for Pod ${podName}, waiting for IP...`);

  // Wait for external IP (up to 3 minutes)
  for (let i = 0; i < 36; i++) {
    await new Promise((r) => setTimeout(r, 5000));

    try {
      const resp = await coreApi.readNamespacedService({
        name: svcName,
        namespace: config.ackNamespace,
      });
      const svc = resp.body || resp;
      const ip = svc.status?.loadBalancer?.ingress?.[0]?.ip;
      if (ip) {
        console.log(`Service ${svcName} got IP: ${ip}`);
        return ip;
      }
    } catch { /* keep waiting */ }
  }

  throw new Error(`Service ${svcName} did not get an IP within 180s`);
}

/**
 * Delete a per-pod Service.
 */
export async function deletePodService(svcName) {
  const { coreApi } = getClient();
  try {
    await coreApi.deleteNamespacedService({
      name: svcName,
      namespace: config.ackNamespace,
    });
    console.log(`Deleted Service ${svcName}`);
  } catch (err) {
    if (err.statusCode !== 404) throw err;
  }
}

/**
 * Delete the per-pod Service for a specific Pod name.
 */
export async function deletePodServiceByName(podName) {
  await deletePodService(`svc-${podName}`);
}

/**
 * Get all pod service mappings: [{ podName, externalIP }].
 */
export async function getPodServiceMap() {
  const services = await listPodServices();
  return services.filter((s) => s.externalIP);
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
