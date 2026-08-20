import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ICP_FILING_NUMBER = '沪ICP备2025109616号-2';
export const MIIT_FILING_URL = 'https://beian.miit.gov.cn/';

const COMPLIANCE_MARKER = 'data-praxys-cn-compliance="icp"';

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function complianceFooterHtml() {
  return `    <footer class="cn-compliance-footer" ${COMPLIANCE_MARKER} aria-label="ICP备案信息">
      <a href="${escapeHtml(MIIT_FILING_URL)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ICP_FILING_NUMBER)}</a>
    </footer>
`;
}

export function stampHtml(html) {
  if (html.includes(COMPLIANCE_MARKER)) return html;
  if (!html.includes('</body>')) {
    throw new Error('Cannot stamp China compliance footer: HTML has no </body>');
  }
  return html.replace('</body>', `${complianceFooterHtml()}  </body>`);
}

async function findHtmlFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findHtmlFiles(entryPath);
    return entry.isFile() && entry.name === 'index.html' ? [entryPath] : [];
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

  await Promise.all(htmlFiles.map(async (htmlPath) => {
    const html = await readFile(htmlPath, 'utf8');
    await writeFile(htmlPath, stampHtml(html), 'utf8');
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
  console.log(`Stamped ICP filing footer into ${stamped.length} HTML files.`);
}
