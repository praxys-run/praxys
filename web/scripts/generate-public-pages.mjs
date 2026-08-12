import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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

function fallbackHtml(locale, pageKey, page) {
  const nav = content.locales[locale].nav;
  const sections = page.sections?.map((section) => `
    <section><h2>${escapeHtml(section.heading)}</h2><p>${escapeHtml(section.body)}</p></section>`).join('') ?? '';
  const summary = page.summaryPoints?.map((point) => `<li>${escapeHtml(point)}</li>`).join('') ?? '';
  const questions = page.questions?.map((item) => `
    <section><h2>${escapeHtml(item.question)}</h2><p>${escapeHtml(item.answer)}</p></section>`).join('') ?? '';
  const extra = pageKey === 'product'
    ? `<section><h2>${escapeHtml(page.dataHeading)}</h2><p>${escapeHtml(page.dataBody)}</p></section>
       <section><h2>${escapeHtml(page.boundaryHeading)}</h2><ul>${page.boundaries.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>`
    : '';
  return `<div id="root">
    <div class="seo-fallback">
      <header><a href="${content.locales[locale].home.path}">Praxys</a>
        <nav><a href="${content.locales[locale].product.path}">${escapeHtml(nav.product)}</a>
        <a href="${content.locales[locale].faq.path}">${escapeHtml(nav.faq)}</a></nav>
      </header>
      <main><h1>${escapeHtml(page.heading)}</h1><p class="seo-lead">${escapeHtml(page.lead)}</p>
        ${summary ? `<ul>${summary}</ul>` : ''}${sections}${extra}${questions}
      </main>
    </div>
  </div>`;
}

function render(locale, pageKey, page) {
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
    .replace('<div id="root"></div>', fallbackHtml(locale, pageKey, page));
  return html;
}

for (const [locale, localeContent] of Object.entries(content.locales)) {
  for (const pageKey of ['home', 'product', 'faq']) {
    const page = localeContent[pageKey];
    const output = page.path === '/'
      ? path.join(distRoot, 'index.html')
      : path.join(distRoot, page.path.slice(1), 'index.html');
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, render(locale, pageKey, page), 'utf8');
  }
}
