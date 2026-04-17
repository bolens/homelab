import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vite';

const apiTarget = process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:3001';

/** At production image build, set `VITE_PUBLIC_ORIGIN` so `og:image` is an absolute URL. */
function publicOriginOgImage(): Plugin {
  return {
    name: 'public-origin-og-image',
    transformIndexHtml(html) {
      const origin = (process.env.VITE_PUBLIC_ORIGIN || '').trim().replace(/\/$/, '');
      if (!origin) return html;
      return html.replace(
        /<meta\s+property="og:image"\s+content="[^"]*"\s*\/?>/,
        `<meta property="og:image" content="${origin}/linkPreview.png" />`,
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), publicOriginOgImage()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'build',
    chunkSizeWarningLimit: 650,
  },
});
