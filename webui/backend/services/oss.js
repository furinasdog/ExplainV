import OSS from 'ali-oss';
import config from '../config.js';

let client = null;

function getClient() {
  if (client) return client;

  client = new OSS({
    region: config.ossRegion,
    accessKeyId: config.ossAccessKeyId,
    accessKeySecret: config.ossAccessKeySecret,
    bucket: config.ossBucket,
  });

  return client;
}

/**
 * Upload a file buffer to OSS and return a signed URL.
 *
 * @param {string} objectKey - e.g. "videos/username/taskId.mp4"
 * @param {Buffer} buffer - file content
 * @returns {string} signed download URL (valid 7 days)
 */
export async function uploadToOss(objectKey, buffer) {
  const oss = getClient();
  await oss.put(objectKey, buffer);

  // Generate a signed URL valid for 7 days
  const url = oss.signatureUrl(objectKey, { expires: 7 * 24 * 3600 });
  console.log(`Uploaded to OSS: ${objectKey}`);
  return url;
}
