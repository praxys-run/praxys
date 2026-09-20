import path from 'path'
import { execFileSync } from 'node:child_process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'
import { lingui } from '@lingui/vite-plugin'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react({
      plugins: [['@lingui/swc-plugin', {}]],
    }),
    tailwindcss(),
    lingui(),
    {
      name: 'prerender-public-documents',
      apply: 'build',
      // Complete HTML before the PWA closeBundle hook records its revisions.
      writeBundle() {
        execFileSync(process.execPath, ['scripts/generate-public-pages.mjs'], {
          cwd: import.meta.dirname,
          // ssrLoadModule uses the development JSX transform, in this child only.
          env: { ...process.env, NODE_ENV: 'development' },
          stdio: 'inherit',
        })
        if (process.env.VITE_DEPLOYMENT_REGION === 'cn') {
          execFileSync(process.execPath, ['scripts/stamp-china-compliance.mjs', 'dist'], {
            cwd: import.meta.dirname,
            env: process.env,
            stdio: 'inherit',
          })
        }
      },
    },
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Praxys',
        short_name: 'Praxys',
        description: 'Science-based training for self-coached runners',
        theme_color: '#4a9e6e',
        background_color: '#fafafa',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      workbox: {
        navigateFallback: '/app-shell.html',
        // Precache the app shell (JS, CSS, HTML, main icon) so repeat
        // visits load instantly from the service worker cache. API
        // requests intentionally excluded — fresh data matters.
        //
        // WOFF2 subsets (108 files, ~4.8 MB) also deliberately excluded:
        // browsers fetch them lazily via unicode-range as glyphs are
        // rendered, so precaching the full set would bloat the install
        // phase + use disk that most users never touch.
        globPatterns: ['**/*.{js,css,html,ico,svg}', ...(process.env.VITE_DEPLOYMENT_REGION === 'cn' ? ['compliance/*.png'] : [])],
        // Canonical navigations must reach the network, including / and /faq/.
        // Otherwise precache routing wins before the network-first route below.
        directoryIndex: null,
        ignoreURLParametersMatching: [],
        navigateFallbackDenylist: [/^\/api\//, /^\/(?:en|zh(?:\/(?:product|faq))?|product|faq|login|terms|privacy|status|verify)?\/?(?:\?.*)?$/],
        runtimeCaching: [{
          urlPattern: ({ request, url }) => request.mode === 'navigate'
            && /^\/(?:en|zh(?:\/(?:product|faq))?|product|faq|login|terms|privacy|status|verify)?\/?$/.test(url.pathname),
          handler: async ({ request, url }) => {
            // Preserve edge redirects and query semantics while online.
            try {
              return await fetch(request)
            } catch (error) {
              // Canonical public paths map to their precached HTML documents.
              // Do not precache /product itself: mainland .run fetches redirect
              // across origins. Its /product/index.html file remains same-origin.
              const storage = globalThis as unknown as {
                caches: { match(url: string, options: { ignoreSearch: boolean }): Promise<Response | undefined> }
              }
              const file = `${url.origin}${url.pathname.replace(/\/+$/, '')}/index.html`
              const cached = await storage.caches.match(file, { ignoreSearch: true })
              if (cached) return cached
              throw error
            }
          },
        }],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    manifest: true,
    // Keep shared utilities out of the chart chunk. Pulling dependencies into a
    // manual Recharts group makes even clsx consumers download the whole chart library.
    rolldownOptions: {
      preserveEntrySignatures: false,
      output: {
        strictExecutionOrder: true,
        codeSplitting: {
          includeDependenciesRecursively: false,
          groups: [
            { name: 'react-vendor', test: /node_modules[\\/](react-router-dom|react-router|react-dom|react)[\\/]/ },
            { name: 'recharts', test: /node_modules[\\/]recharts[\\/]/ },
            { name: 'query', test: /node_modules[\\/]@tanstack[\\/](react-query|query-core)[\\/]/ },
          ],
        },
      },
    },
  },
})
