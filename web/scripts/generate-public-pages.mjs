import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { lingui } from '@lingui/vite-plugin';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const distRoot = path.join(webRoot, 'dist');
const content = JSON.parse(await readFile(path.join(webRoot, 'public', 'seo-content.json'), 'utf8'));
const shell = await readFile(path.join(distRoot, 'index.html'), 'utf8');

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function replaceMeta(html, selector, value) {
  const escaped = escapeHtml(value);
  const pattern = selector === 'description'
    ? /<meta name="description"[^>]*>/i
    : new RegExp(`<meta property="${selector}"[^>]*>`, 'i');
  const name = selector === 'description' ? 'name' : 'property';
  return html.replace(pattern, `<meta ${name}="${selector}" content="${escaped}" />`);
}

function structuredData(pageKey, page, canonical) {
  if (pageKey === 'faq') {
    return {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: page.questions.map((item) => ({
        '@type': 'Question',
        name: item.question,
        acceptedAnswer: { '@type': 'Answer', text: item.answer },
      })),
    };
  }
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Organization',
        name: content.site.name,
        url: content.site.baseUrl,
        logo: `${content.site.baseUrl}/favicon.svg`,
      },
      {
        '@type': 'SoftwareApplication',
        name: content.site.name,
        applicationCategory: 'HealthApplication',
        operatingSystem: 'Web',
        url: canonical,
        description: page.description,
      },
    ],
  };
}


function render(locale, pageKey, page, pathname, renderPublicDocument) {
  const localeContent = content.locales[locale];
  const canonical = `${content.site.baseUrl}${page.path}`;
  const alternate = `${content.site.baseUrl}${page.alternatePath}`;
  let html = shell
    .replace(/<html lang="[^"]*">/i, `<html lang="${localeContent.language}">`)
    .replace(/<title>.*?<\/title>/is, `<title>${escapeHtml(page.title)}</title>`);
  html = replaceMeta(html, 'description', page.description);
  html = replaceMeta(html, 'og:title', page.title);
  html = replaceMeta(html, 'og:description', page.description);
  html = replaceMeta(html, 'og:url', canonical);
  html = replaceMeta(html, 'og:locale', locale === 'zh' ? 'zh_CN' : 'en_US');
  html = html
    .replace(/<meta name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(page.title)}" />`)
    .replace(/<meta name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(page.description)}" />`)
    .replace('</head>', `    <meta name="robots" content="index, follow, max-image-preview:large" />
    <link rel="canonical" href="${canonical}" />
    <link rel="alternate" hreflang="${localeContent.language}" href="${canonical}" />
    <link rel="alternate" hreflang="${locale === 'zh' ? 'en' : 'zh-CN'}" href="${alternate}" />
    ${pageKey === 'home' ? `<link rel="alternate" hreflang="x-default" href="${content.site.baseUrl}/" />` : ''}
    <script id="praxys-structured-data" type="application/ld+json">${JSON.stringify(structuredData(pageKey, page, canonical)).replaceAll('<', '\\u003c')}</script>
  </head>`)
    .replace('<div id="root"></div>', `<div id="root" data-praxys-public-page="${pageKey}" data-praxys-public-locale="${locale}">${renderPublicDocument(pathname, china)}</div>`);
  return html;
}

const china = process.env.VITE_DEPLOYMENT_REGION === 'cn';
// ssrLoadModule uses Vite's development JSX transform in this build-only child.
process.env.NODE_ENV = 'development';
// Rendering happens only during the build. Nothing is deployed as a server function.
const server = await createServer({
  configFile: false,
  root: webRoot,
  plugins: [react({ plugins: [['@lingui/swc-plugin', {}]] }), lingui()],
  resolve: { alias: { '@': path.join(webRoot, 'src') } },
  server: { middlewareMode: true },
  appType: 'custom',
  optimizeDeps: { noDiscovery: true, entries: [] },
});
try {
  const { renderPublicDocument, renderAppShell } = await server.ssrLoadModule('/src/public-render.tsx');
  const appShell = shell
    .replace(/<html lang="[^"]*">/i, `<html lang="${china ? 'zh-CN' : 'en'}">`)
    .replace(/<title>.*?<\/title>/is, '<title>Praxys</title>')
    .replace('<div id="root"></div>', `<div id="root">${renderAppShell()}</div>`)
    .replace('</head>', '<meta name="robots" content="noindex, nofollow" /></head>');
  await writeFile(path.join(distRoot, 'app-shell.html'), appShell, 'utf8');
  // Public application entrances need a visible static regional filing even
  // without JavaScript. Private routes keep the separate hidden-footer shell.
  for (const route of ['login', 'terms', 'privacy', 'status', 'verify']) {
    await mkdir(path.join(distRoot, route), { recursive: true });
    await writeFile(path.join(distRoot, route, 'index.html'), appShell, 'utf8');
  }
  for (const [locale, localeContent] of Object.entries(content.locales)) {
    for (const pageKey of ['home', 'product', 'faq']) {
      const page = localeContent[pageKey];
      const actualLocale = page.path === '/' && china ? 'zh' : locale;
      const actualPage = content.locales[actualLocale][pageKey];
      const output = page.path === '/' ? path.join(distRoot, 'index.html') : path.join(distRoot, page.path.slice(1), 'index.html');
      await mkdir(path.dirname(output), { recursive: true });
      let html = render(actualLocale, pageKey, actualPage, page.path, renderPublicDocument);
      if (page.path === '/') {
        // Compatibility for old explicit-English links. New language links use /en.
        html = html.replace('</head>', `<script>if(new URLSearchParams(location.search).get('lang')==='en'){document.documentElement.setAttribute('data-public-language-redirect','');location.replace('/en'+location.search+location.hash)}</script><style>html[data-public-language-redirect] #root{visibility:hidden}</style></head>`);
      }
      await writeFile(output, html, 'utf8');
    }
  }
  await mkdir(path.join(distRoot, 'en'), { recursive: true });
  await writeFile(path.join(distRoot, 'en', 'index.html'), render('en', 'home', content.locales.en.home, '/en', renderPublicDocument), 'utf8');
} finally {
  await server.close();
}
