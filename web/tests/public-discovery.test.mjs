import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const content = JSON.parse(
  await readFile(new URL('../public/seo-content.json', import.meta.url), 'utf8'),
);
const robots = await readFile(new URL('../public/robots.txt', import.meta.url), 'utf8');
const sitemap = await readFile(new URL('../public/sitemap.xml', import.meta.url), 'utf8');

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

test('FAQ content covers product, privacy, and mainland China discovery', () => {
  for (const locale of Object.values(content.locales)) {
    const faqText = JSON.stringify(locale.faq);
    assert.match(faqText, /managed plan|托管计划/i);
    assert.match(faqText, /Labs/i);
    assert.match(faqText, /privacy|隐私/i);
    assert.match(faqText, /praxys\.cn/i);
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
