import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    // The procedural instrument scene is isolated behind a lazy import.
    chunkSizeWarningLimit: 850,
  },
});
