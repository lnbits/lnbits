import {defineConfig} from 'vitest/config'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom'
  },
  define: {
    'process.env': {} // Replace process.env with an empty object for browser builds
  },
  build: {
    lib: {
      entry: 'lnbits/static/components/main.js',
      name: 'LnbitsComponents',
      fileName: 'components', // Output file name (build.js)
      formats: ['umd']
    },
    minify: 'terser', // Optional: minify the output
    rollupOptions: {
      // If you have external dependencies, mark them here
      external: []
    },
    outDir: 'lnbits/static/modules' // Output folder
  }
})
