import { TERMS_VERSION } from './legal';

export const CHINA_PROCESSING_NOTICE_VERSION = TERMS_VERSION;
export const CHINA_PROCESSING_NOTICE_STORAGE_KEY =
  'praxys.cn-processing-notice';

let acknowledgedForThisLaunch = false;

/** Return whether the current mainland-China processing notice was read. */
export function hasAcknowledgedChinaProcessingNotice(): boolean {
  if (acknowledgedForThisLaunch) return true;
  try {
    return (
      wx.getStorageSync<string>(CHINA_PROCESSING_NOTICE_STORAGE_KEY)
      === CHINA_PROCESSING_NOTICE_VERSION
    );
  } catch {
    return false;
  }
}

/** Record a local pre-transfer read acknowledgement for the current version. */
export function acknowledgeChinaProcessingNotice(): void {
  acknowledgedForThisLaunch = true;
  try {
    wx.setStorageSync(
      CHINA_PROCESSING_NOTICE_STORAGE_KEY,
      CHINA_PROCESSING_NOTICE_VERSION,
    );
  } catch {
    // Keep the launch-scoped receipt. A future launch will show the notice
    // again if persistent storage is unavailable.
  }
}
