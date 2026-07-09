window.app.component('lnbits-admin-wasm-limit-config', {
  props: ['form-data'],
  template: '#lnbits-admin-wasm-limit-config',
  data() {
    return {
      wasmRuntimeLimitGroups: [
        {
          title: 'Execution',
          fields: [
            {
              name: 'wasm_runtime_max_execution_ms',
              label: 'Max execution time (ms)',
              description:
                'Maximum wall-clock time allowed for one WASM invocation.'
            },
            {
              name: 'wasm_runtime_max_fuel',
              label: 'Max fuel',
              description:
                'Maximum Wasmtime instruction budget for one invocation.'
            },
            {
              name: 'wasm_runtime_max_wasm_stack_bytes',
              label: 'Max WASM stack (bytes)',
              description: 'Maximum stack space for WASM calls and recursion.'
            }
          ]
        },
        {
          title: 'Memory and Data Size',
          fields: [
            {
              name: 'wasm_runtime_max_memory_bytes',
              label: 'Max memory (bytes)',
              description: 'Maximum WASM linear memory per invocation.'
            },
            {
              name: 'wasm_runtime_max_request_bytes',
              label: 'Max request size (bytes)',
              description:
                'Maximum serialized input payload accepted before execution.'
            },
            {
              name: 'wasm_runtime_max_response_bytes',
              label: 'Max response size (bytes)',
              description:
                'Maximum serialized response returned by a WASM export.'
            }
          ]
        },
        {
          title: 'Wasmtime Objects',
          fields: [
            {
              name: 'wasm_runtime_max_table_elements',
              label: 'Max table elements',
              description: 'Maximum total elements allowed in WASM tables.'
            },
            {
              name: 'wasm_runtime_max_instances',
              label: 'Max instances',
              description:
                'Maximum WebAssembly instances allowed inside one store.'
            },
            {
              name: 'wasm_runtime_max_tables',
              label: 'Max tables',
              description:
                'Maximum WebAssembly tables allowed inside one store.'
            },
            {
              name: 'wasm_runtime_max_memories',
              label: 'Max memories',
              description:
                'Maximum WebAssembly linear memories allowed inside one store.'
            }
          ]
        },
        {
          title: 'Concurrency',
          fields: [
            {
              name: 'wasm_runtime_max_concurrent_invocations',
              label: 'Max concurrent invocations',
              description: 'Maximum running WASM invocations across the server.'
            },
            {
              name: 'wasm_runtime_max_concurrent_invocations_per_extension',
              label: 'Max concurrent per extension',
              description: 'Maximum running WASM invocations for one extension.'
            },
            {
              name: 'wasm_runtime_max_concurrent_invocations_per_user',
              label: 'Max concurrent per user',
              description: 'Maximum running WASM invocations for one user.'
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
                'Maximum total calls from WASM into LNbits host APIs.'
            },
            {
              name: 'wasm_runtime_max_http_calls',
              label: 'Max HTTP calls',
              description: 'Maximum outbound HTTP host calls per invocation.'
            },
            {
              name: 'wasm_runtime_max_storage_calls',
              label: 'Max storage calls',
              description: 'Maximum storage host calls per invocation.'
            },
            {
              name: 'wasm_runtime_max_wallet_calls',
              label: 'Max wallet calls',
              description: 'Maximum wallet/payment host calls per invocation.'
            }
          ]
        },
        {
          title: 'HTTP',
          fields: [
            {
              name: 'wasm_runtime_http_timeout_ms',
              label: 'HTTP timeout (ms)',
              description: 'Maximum time allowed for one WASM HTTP request.'
            },
            {
              name: 'wasm_runtime_max_http_response_bytes',
              label: 'Max HTTP response size (bytes)',
              description:
                'Maximum response body size accepted from one WASM HTTP request.'
            }
          ]
        }
      ]
    }
  }
})
