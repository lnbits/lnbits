const assert = require('node:assert/strict')
const {readFileSync} = require('node:fs')
const {test} = require('node:test')
const vm = require('node:vm')

function harness() {
  const context = {window: {}, TextEncoder}
  vm.runInNewContext(
    readFileSync('lnbits/static/js/wasm-extension-component.js', 'utf8'),
    context
  )
  const instance = {bridge: {extensionId: 'invoiceswasm'}}
  for (const [name, method] of Object.entries(
    context.window.WasmExtensionComponent.methods
  ))
    instance[name] = method.bind(instance)
  return instance
}

test('CSV escapes quotes, newlines, formulas, and leading-space formulas', () => {
  const instance = harness()
  const result = instance.csvDocument({
    filename: 'tickets.csv',
    columns: ['Name', 'Message'],
    rows: [
      ['A "quote"', '=HYPERLINK("https://evil")'],
      ['line\nbreak', '  +SUM(1)']
    ]
  })
  assert.match(result.text, /"A ""quote"""/)
  assert.match(result.text, /"'=HYPERLINK/)
  assert.match(result.text, /"'  \+SUM/)
  assert.match(result.text, /"line\nbreak"/)
})

test('exports reject paths, executable formats, malformed rows and oversized payloads', () => {
  const instance = harness(),
    base = {filename: 'export.csv', columns: ['A'], rows: [['value']]}
  for (const filename of ['../export.csv', 'x.html', '/tmp/x.csv', 'x.csv.exe'])
    assert.throws(() => instance.csvDocument({...base, filename}))
  for (const rows of [
    [[{html: '<script>'}]],
    [['a', 'b']],
    [['a'.repeat(1048576)]]
  ])
    assert.throws(() => instance.csvDocument({...base, rows}))
})

test('printing only accepts bounded structured text and tables', () => {
  const instance = harness(),
    base = {
      title: 'Invoice',
      lines: ['<script>text</script>'],
      columns: ['Item'],
      rows: [['<img src=x onerror=alert(1)>']]
    }
  const result = instance.printDocument(base)
  assert.equal(result.lines[0], '<script>text</script>')
  assert.throws(() =>
    instance.printDocument({...base, lines: [{html: 'unsafe'}]})
  )
  assert.throws(() => instance.printDocument({...base, title: 'x'.repeat(201)}))
})

test('bridge dispatch sends errors for invalid exports before triggering a browser action', async () => {
  const instance = harness(),
    replies = []
  await instance.handleBridgeRequest(
    {
      type: 'lnbits-extension:request',
      id: '1',
      action: 'ui.download_csv',
      filename: 'evil.html'
    },
    r => replies.push(r)
  )
  assert.equal(replies[0].ok, false)
  assert.match(replies[0].error, /Invalid CSV filename/)
})

test('cancelled export never touches the document or creates a download URL', async () => {
  const instance = harness()
  instance.confirmDocumentAction = async () => false
  const result = await instance.downloadCsv({
    filename: 'export.csv',
    columns: ['A'],
    rows: [['value']]
  })
  assert.equal(result.cancelled, true)
})
