window.app.component('lnbits-admin-wasm-limit-config', {
  props: ['form-data'],
  template: '#lnbits-admin-wasm-limit-config',
  data() {
    return {
      wasmLimitInfoDialog: {
        show: false,
        title: '',
        details: ''
      },
      wasmRuntimeLimitGroups: [
        {
          title: 'Execution',
          fields: [
            {
              name: 'wasm_runtime_max_execution_ms',
              label: 'Max execution time (ms)',
              description:
                'Maximum wall-clock time allowed for one WASM invocation.',
              details:
                'This is the elapsed time from starting the invocation until the export returns. When the limit is reached LNbits requests an interrupt and records the invocation as timed out if it cannot finish quickly. Use this to stop long sleeps, slow host calls, and CPU loops that run for too long.'
            },
            {
              name: 'wasm_runtime_max_fuel',
              label: 'Max fuel',
              description:
                'Maximum Wasmtime instruction budget for one invocation.',
              details:
                'Fuel is Wasmtime instruction budgeting. It is more deterministic than wall-clock time for CPU-heavy loops because each executed instruction consumes budget. Set this low enough to stop busy loops, but high enough for legitimate extension startup and JSON processing.'
            },
            {
              name: 'wasm_runtime_max_wasm_stack_bytes',
              label: 'Max WASM stack (bytes)',
              description: 'Maximum stack space for WASM calls and recursion.',
              details:
                'This limits stack used by WebAssembly function calls. It protects the server from deep recursion or very large call chains in extension code. If legitimate extensions fail with stack overflow traps, raise this carefully.'
            }
          ]
        },
        {
          title: 'Memory and Data Size',
          fields: [
            {
              name: 'wasm_runtime_max_memory_bytes',
              label: 'Max memory (bytes)',
              description: 'Maximum WASM linear memory per invocation.',
              details:
                'This caps the linear memory visible to the WASM module. It limits memory.grow and can make instantiation fail if the module asks for too much memory up front. This does not include every byte used by the Python process or Wasmtime engine internals.'
            },
            {
              name: 'wasm_runtime_max_request_bytes',
              label: 'Max request size (bytes)',
              description:
                'Maximum serialized input payload accepted before execution.',
              details:
                'This caps the serialized payload passed into a WASM export before execution starts. It protects against huge HTTP bodies, oversized event data, and expensive JSON parsing. Requests above this limit should be rejected before invoking the extension.'
            },
            {
              name: 'wasm_runtime_max_response_bytes',
              label: 'Max response size (bytes)',
              description:
                'Maximum serialized response returned by a WASM export.',
              details:
                'This caps the JSON or string response returned by the WASM export. It prevents extensions from returning huge responses that consume memory, slow down API calls, or overload the browser. Responses above this limit are treated as invalid.'
            }
          ]
        },
        {
          title: 'Wasmtime Objects',
          fields: [
            {
              name: 'wasm_runtime_max_table_elements',
              label: 'Max table elements',
              description: 'Maximum total elements allowed in WASM tables.',
              details:
                'Tables store references used by WebAssembly, commonly function references. Limiting table elements prevents a module from allocating very large reference tables. Each table element also has host memory overhead.'
            },
            {
              name: 'wasm_runtime_max_instances',
              label: 'Max instances',
              description:
                'Maximum WebAssembly instances allowed inside one store.',
              details:
                'This limits how many WebAssembly instances can be created inside one Wasmtime store. LNbits normally needs one instance per invocation, so a low value is expected. Raising it should only be needed if the runtime starts supporting modules that instantiate other modules.'
            },
            {
              name: 'wasm_runtime_max_tables',
              label: 'Max tables',
              description:
                'Maximum WebAssembly tables allowed inside one store.',
              details:
                'This limits the number of WebAssembly tables in the store. It is separate from table elements: one setting limits the number of tables, the other limits their total size. Keep this small unless a component model module legitimately needs more tables.'
            },
            {
              name: 'wasm_runtime_max_memories',
              label: 'Max memories',
              description:
                'Maximum WebAssembly linear memories allowed inside one store.',
              details:
                'This limits how many separate linear memories a module can create. Most extensions should need only one memory. Keep this small to reduce memory accounting complexity and prevent multi-memory abuse.'
            }
          ]
        },
        {
          title: 'Concurrency',
          fields: [
            {
              name: 'wasm_runtime_max_concurrent_invocations',
              label: 'Max concurrent invocations',
              description:
                'Maximum running WASM invocations across the server.',
              details:
                'This is the global cap for running WASM invocations across all extensions and users. It protects the LNbits process from thread exhaustion, CPU pressure, and too many simultaneous stores. New invocations should be rejected or queued once this is reached.'
            },
            {
              name: 'wasm_runtime_max_concurrent_invocations_per_extension',
              label: 'Max concurrent per extension',
              description:
                'Maximum running WASM invocations for one extension.',
              details:
                'This caps how many invocations a single extension can run at once. It prevents one malicious or buggy extension from consuming the whole global concurrency budget. Set it lower than the global limit.'
            },
            {
              name: 'wasm_runtime_max_concurrent_invocations_per_user',
              label: 'Max concurrent per user',
              description: 'Maximum running WASM invocations for one user.',
              details:
                'This caps concurrent invocations attributed to one user. It helps protect against a user repeatedly clicking, refreshing, or scripting extension calls. Invocations without a user can still be governed by the global and per-extension limits.'
            }
          ]
        },
        {
          title: 'Host Calls',
          fields: [
            {
              name: 'wasm_runtime_max_host_calls',
              label: 'Max host calls',
              description:
                'Maximum total calls from WASM into LNbits host APIs.',
              details:
                'This is the total budget for calls from the WASM module into LNbits host APIs during one invocation. It should count all categories together. It limits chatty extensions and prevents tight loops that repeatedly call back into Python.'
            },
            {
              name: 'wasm_runtime_max_http_calls',
              label: 'Max HTTP calls',
              description: 'Maximum outbound HTTP host calls per invocation.',
              details:
                'This caps outbound HTTP requests made through the host API during one invocation. It reduces SSRF blast radius, protects network resources, and limits slow external dependencies. It should be enforced together with HTTP timeout and response-size limits.'
            },
            {
              name: 'wasm_runtime_max_storage_calls',
              label: 'Max storage calls',
              description: 'Maximum storage host calls per invocation.',
              details:
                'This caps extension storage operations during one invocation. It protects the database from excessive reads and writes triggered by malicious loops. Use it with storage payload-size limits if those are added later.'
            },
            {
              name: 'wasm_runtime_max_wallet_calls',
              label: 'Max wallet calls',
              description: 'Maximum wallet/payment host calls per invocation.',
              details:
                'This caps wallet and payment-related host calls during one invocation. These calls are security-sensitive and may touch balances, invoices, or payments. Keep this conservative and rely on explicit permissions for what the extension is allowed to do.'
            }
          ]
        },
        {
          title: 'HTTP',
          fields: [
            {
              name: 'wasm_runtime_http_timeout_ms',
              label: 'HTTP timeout (ms)',
              description: 'Maximum time allowed for one WASM HTTP request.',
              details:
                'This is the per-request timeout for HTTP calls made through the WASM host API. It prevents a slow remote server from holding an invocation open indefinitely. The total invocation timeout still applies across all work.'
            },
            {
              name: 'wasm_runtime_max_http_response_bytes',
              label: 'Max HTTP response size (bytes)',
              description:
                'Maximum response body size accepted from one WASM HTTP request.',
              details:
                'This caps the response body accepted from each HTTP call made by an extension. It protects memory and parsing time when a remote server returns a very large body. Responses above the limit should fail the host call.'
            }
          ]
        }
      ]
    }
  },
  methods: {
    showWasmLimitInfo(field) {
      this.wasmLimitInfoDialog = {
        show: true,
        title: field.label,
        details: field.details
      }
    }
  }
})
