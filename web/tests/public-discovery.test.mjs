import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const content = JSON.parse(
  await readFile(new URL('../public/seo-content.json', import.meta.url), 'utf8'),
);
const robots = await readFile(new URL('../public/robots.txt', import.meta.url), 'utf8');
const sitemap = await readFile(new URL('../public/sitemap.xml', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8');
const landingSource = await readFile(new URL('../src/pages/Landing.tsx', import.meta.url), 'utf8');

test('public pages have unique canonical paths and metadata', () => {
  const pages = Object.values(content.locales).flatMap((locale) => [
    locale.home,
    locale.product,
    locale.faq,
  ]);
  assert.equal(new Set(pages.map((page) => page.path)).size, pages.length);
  assert.equal(new Set(pages.map((page) => page.title)).size, pages.length);
  assert.equal(new Set(pages.map((page) => page.description)).size, pages.length);
  for (const page of pages) {
    assert.ok(page.heading.length > 10);
    assert.ok(page.lead.length > 40);
    if (page.headingAccent) assert.ok(page.heading.endsWith(page.headingAccent));
  }
});

test('public product copy names every current platform connection', () => {
  for (const locale of Object.values(content.locales)) {
    const productText = JSON.stringify(locale.product);
    const faqText = JSON.stringify(locale.faq);
    for (const platform of ['Garmin', 'Strava', 'COROS', 'Stryd', 'Oura']) {
      assert.match(productText, new RegExp(platform, 'i'));
      assert.match(faqText, new RegExp(platform, 'i'));
    }
  }
});

test('managed plan copy names current Garmin and Stryd delivery', () => {
  for (const locale of Object.values(content.locales)) {
    const managedSection = locale.product.sections.find((section) =>
      /Garmin/i.test(section.body) && /Stryd/i.test(section.body)
    );
    const managedQuestion = locale.faq.questions.find((item) =>
      /managed.*plan|托管.*计划/i.test(item.question)
    );
    assert.ok(managedSection);
    assert.ok(managedQuestion);
    for (const platform of ['Garmin', 'Stryd']) {
      assert.match(managedSection.body, new RegExp(platform, 'i'));
      assert.match(managedQuestion.answer, new RegExp(platform, 'i'));
    }
  }
});

test('FAQ stays focused on product fit, connections, controlled AI, plans, and data use', () => {
  for (const locale of Object.values(content.locales)) {
    const faqText = JSON.stringify(locale.faq);
    assert.equal(locale.faq.questions.length, 5);
    assert.match(faqText, /managed.*plan|托管.*计划/i);
    assert.match(faqText, /sport science|运动科学/i);
    assert.match(faqText, /AI/i);
    assert.match(faqText, /sell athlete data|出售跑者数据/i);
    assert.doesNotMatch(faqText, /power meter|功率计/i);
    assert.doesNotMatch(faqText, /praxys\.cn/i);
  }
});

test('robots and sitemap expose only the canonical public surface', () => {
  for (const path of ['/product', '/faq', '/zh', '/zh/product', '/zh/faq']) {
    assert.match(sitemap, new RegExp(`https://www\\.praxys\\.run${path}`));
  }
  for (const path of ['/login', '/today', '/training', '/admin', '/labs']) {
    assert.match(robots, new RegExp(`Disallow: ${path}`));
    assert.doesNotMatch(sitemap, new RegExp(`www\\.praxys\\.run${path}`));
  }
});

test('public language switching uses explicit locale routes', () => {
  assert.match(appSource, /get\('lang'\) === 'en'/);
  assert.match(landingSource, /window\.location\.assign\('\/\?lang=en'\)/);
  assert.match(landingSource, /window\.location\.assign\('\/zh'\)/);
});
