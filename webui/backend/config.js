import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '../.env') });

export default {
  port: parseInt(process.env.PORT || '3000'),
  jwtSecret: process.env.JWT_SECRET || 'dev-secret-change-me',

  // ACK cluster
  kubeconfigPath: process.env.KUBECONFIG_PATH
    ? resolve(__dirname, process.env.KUBECONFIG_PATH)
    : resolve(__dirname, '../kubeconfig.yaml'),
  ackNamespace: process.env.ACK_NAMESPACE || 'explainv',
  ackDeployment: process.env.ACK_DEPLOYMENT || 'explainv-api',
  ackServiceUrl: process.env.ACK_SERVICE_URL || 'http://explainv-api.explainv.svc.cluster.local:8000',

  // OSS
  ossRegion: process.env.OSS_REGION || 'oss-cn-hangzhou',
  ossBucket: process.env.OSS_BUCKET || 'explainv-videos',
  ossAccessKeyId: process.env.OSS_ACCESS_KEY_ID || '',
  ossAccessKeySecret: process.env.OSS_ACCESS_KEY_SECRET || '',

  // Paths
  dataDir: resolve(__dirname, 'data'),
  uploadDir: resolve(__dirname, 'data/uploads'),
};
