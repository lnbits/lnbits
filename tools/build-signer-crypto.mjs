import {build} from 'esbuild'
import {readFileSync} from 'node:fs'
const check = process.argv.includes('--check')
const result = await build({
  write: !check,
  entryPoints: ['lnbits/onchain/static/js/session-crypto.js'],
  outfile: 'lnbits/onchain/static/js/session-crypto.bundle.js',
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  minify: true,
  legalComments: 'linked'
})

if (check) {
  for (const file of result.outputFiles) {
    if (!Buffer.from(file.contents).equals(readFileSync(file.path)))
      throw new Error(`Stale signer crypto bundle: ${file.path}`)
  }
}
