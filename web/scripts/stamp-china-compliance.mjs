import { copyFile, mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ICP_FILING_NUMBER = '沪ICP备2025109616号-2';
export const MIIT_FILING_URL = 'https://beian.miit.gov.cn/';
export const PUBLIC_SECURITY_FILING_NUMBER = '沪公网安备31011802006255号';
export const PUBLIC_SECURITY_FILING_URL = 'https://beian.mps.gov.cn/#/query/webSearch?code=31011802006255';
export const PUBLIC_SECURITY_ICON_PATH = '/compliance/public-security-filing.png';
export const CHINA_DEPLOYMENT_REGION = 'cn';

const COMPLIANCE_MARKER = 'data-praxys-cn-compliance="icp"';
const DEPLOYMENT_MARKER = `name="praxys-deployment-region" content="${CHINA_DEPLOYMENT_REGION}"`;

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function complianceFooterHtml(hidden = false) {
  return `    <footer class="cn-compliance-footer" ${COMPLIANCE_MARKER}${hidden ? ' hidden' : ''} aria-label="网站备案信息">
      <a href="${escapeHtml(MIIT_FILING_URL)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ICP_FILING_NUMBER)}</a>
      <a href="${escapeHtml(PUBLIC_SECURITY_FILING_URL)}" target="_blank" rel="noopener noreferrer"><img src="${PUBLIC_SECURITY_ICON_PATH}" width="20" height="20" alt="" />${escapeHtml(PUBLIC_SECURITY_FILING_NUMBER)}</a>
    </footer>
`;
}

export function stampHtml(html, footerHidden = false) {
  let stamped = html;
  if (!stamped.includes(DEPLOYMENT_MARKER)) {
    if (!stamped.includes('</head>')) {
      throw new Error('Cannot stamp China deployment marker: HTML has no </head>');
    }
    stamped = stamped.replace(
      '</head>',
      `    <meta ${DEPLOYMENT_MARKER} />\n  </head>`,
    );
  }
  if (!stamped.includes(COMPLIANCE_MARKER)) {
    if (!stamped.includes('</body>')) {
      throw new Error('Cannot stamp China compliance footer: HTML has no </body>');
    }
    stamped = stamped.replace(
      '</body>',
      `${complianceFooterHtml(footerHidden)}  </body>`,
    );
  }
  return stamped;
}

async function findHtmlFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findHtmlFiles(entryPath);
    return entry.isFile() && ['index.html', 'app-shell.html'].includes(entry.name) ? [entryPath] : [];
  }));
  return nested.flat();
}

export async function stampChinaCompliance(directory) {
  const htmlFiles = await findHtmlFiles(directory);
  if (htmlFiles.length === 0) {
    throw new Error(
      `Cannot stamp China compliance footer: no route index.html files in ${directory}`,
    );
  }

  const iconDestination = path.join(directory, PUBLIC_SECURITY_ICON_PATH.slice(1));
  await mkdir(path.dirname(iconDestination), { recursive: true });
  await copyFile(new URL('./assets/public-security-filing.png', import.meta.url), iconDestination);

  await Promise.all(htmlFiles.map(async (htmlPath) => {
    const html = await readFile(htmlPath, 'utf8');
    await writeFile(htmlPath, stampHtml(html, path.basename(htmlPath) === 'app-shell.html'), 'utf8');
  }));
  return htmlFiles;
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (invokedPath === fileURLToPath(import.meta.url)) {
  const target = process.argv[2];
  if (!target) {
    throw new Error('Usage: node web/scripts/stamp-china-compliance.mjs <dist-directory>');
  }
  const stamped = await stampChinaCompliance(path.resolve(target));
  console.log(`Stamped ICP and public-security filing footer into ${stamped.length} HTML files.`);
}
