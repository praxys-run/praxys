import { apiGet } from './api-client';

const EXPORT_FILE_NAME = 'praxys-data-export.json';
const LEGACY_EXPORT_FILE_RE = /^praxys-data-export-\d+\.json$/;

function writeExportFile(filePath: string, data: string): Promise<void> {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().writeFile({
      filePath,
      data,
      encoding: 'utf8',
      success: () => resolve(),
      fail: reject,
    });
  });
}

function shareExportFile(filePath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    wx.shareFileMessage({
      filePath,
      fileName: 'praxys-data-export.json',
      success: () => resolve(),
      fail: reject,
    });
  });
}

function listExportDirectory(): Promise<string[]> {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readdir({
      dirPath: wx.env.USER_DATA_PATH,
      success: (result) => resolve(result.files),
      fail: reject,
    });
  });
}

function removeExportFile(filePath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().unlink({
      filePath,
      success: () => resolve(),
      fail: reject,
    });
  });
}

async function removeStoredExports(): Promise<void> {
  const names = await listExportDirectory();
  const exportNames = names.filter(
    (name) => name === EXPORT_FILE_NAME || LEGACY_EXPORT_FILE_RE.test(name),
  );
  for (const name of exportNames) {
    await removeExportFile(`${wx.env.USER_DATA_PATH}/${name}`);
  }
}

/** Fetch the authenticated account export, save it locally, and open WeChat's share sheet. */
export async function exportAndShareMyData(): Promise<void> {
  await removeStoredExports();
  const data = await apiGet<unknown>('/api/me/export');
  const filePath = `${wx.env.USER_DATA_PATH}/${EXPORT_FILE_NAME}`;
  await writeExportFile(filePath, JSON.stringify(data, null, 2));

  let shareFailure: unknown;
  try {
    await shareExportFile(filePath);
  } catch (error) {
    shareFailure = error;
  }

  let cleanupFailure: unknown;
  try {
    await removeExportFile(filePath);
  } catch (error) {
    cleanupFailure = error;
  }

  if (shareFailure) {
    if (cleanupFailure) {
      console.error('[data-rights] export share and cleanup both failed', cleanupFailure);
    }
    throw shareFailure;
  }
  if (cleanupFailure) throw cleanupFailure;
}
