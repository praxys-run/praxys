import {
  CHINA_PROCESSING_NOTICE_VERSION,
  hasAcknowledgedChinaProcessingNotice,
} from './china-processing';
import { isChinaFrontendDeployment } from './runtime-region';
import { WEB_SOURCE_SHA, WEB_VERSION } from './version';
import { TERMS_CONTENT_DIGEST } from './legal';

export const TERMS_REQUIRED_EVENT = 'praxys:terms-required';
export const CN_PRIVACY_CONTRACT_VERSION = 'cn-privacy-v2';

/** Identify a reviewed China web build after its local notice gate clears. */
export function getChinaClientHeaders(): Record<string, string> {
  if (
    !isChinaFrontendDeployment()
    || !hasAcknowledgedChinaProcessingNotice()
  ) {
    return {};
  }
  return {
    'X-Praxys-Client': 'cn-web',
    'X-Praxys-Client-Version': WEB_VERSION,
    'X-Praxys-Source-Sha': WEB_SOURCE_SHA,
    'X-Praxys-Notice-Version': CHINA_PROCESSING_NOTICE_VERSION,
    'X-Praxys-Policy-Digest': TERMS_CONTENT_DIGEST,
    'X-Praxys-Api-Contract': CN_PRIVACY_CONTRACT_VERSION,
  };
}
