;(function () {
  function translate(translateFn, key) {
    return translateFn ? translateFn(key) : key
  }

  function permissionI18nKey(permission) {
    return `extension_permission_${permission.id.replace(/[^A-Za-z0-9]/g, '_')}`
  }

  function permissionLabel(permission, translateFn) {
    const key = permissionI18nKey(permission)
    const label = translate(translateFn, key)
    return label === key ? permission.id : label
  }

  function permissionManifestDescription(permission) {
    return typeof permission.description === 'string'
      ? permission.description
      : ''
  }

  function lowRisk(translateFn) {
    return {
      level: 'low',
      color: 'grey-6',
      label: translate(translateFn, 'extension_permission_risk_low'),
      warning: ''
    }
  }

  function mediumRisk(translateFn) {
    return {
      level: 'medium',
      color: 'warning',
      label: translate(translateFn, 'extension_permission_risk_medium'),
      warning: ''
    }
  }

  function highRisk(translateFn, warningKey) {
    return {
      level: 'high',
      color: 'negative',
      label: translate(translateFn, 'extension_permission_risk_high'),
      warning: translate(translateFn, warningKey)
    }
  }

  function extensionDisplayName(extensions, extensionId) {
    const extension = (extensions || []).find(
      extension => extension.id === extensionId
    )
    return extension?.name || extensionId
  }

  function extensionApiPermissionTargets(permission, extensions) {
    const extensionPolicies = permission.policies
    if (!Array.isArray(extensionPolicies)) return []
    return extensionPolicies
      .map(extension => {
        const extensionId =
          typeof extension === 'string' ? extension : extension?.id
        if (!extensionId) return null
        const access =
          typeof extension === 'string'
            ? ['read']
            : Array.isArray(extension.access) && extension.access.length
              ? extension.access
              : ['read']
        return {
          id: extensionId,
          name: extensionDisplayName(extensions, extensionId),
          access
        }
      })
      .filter(Boolean)
  }

  function permissionRiskForPermission(permission, extensions, translateFn) {
    if (permission.id === 'wallet.pay_invoice') {
      return highRisk(
        translateFn,
        'extension_permission_warning_wallet_pay_invoice'
      )
    }
    if (permission.id === 'extension.api.request') {
      const hasWriteAccess = extensionApiPermissionTargets(
        permission,
        extensions
      ).some(target => target.access.includes('write'))
      return hasWriteAccess
        ? highRisk(
            translateFn,
            'extension_permission_warning_extension_api_request_write'
          )
        : mediumRisk(translateFn)
    }
    if (permission.id === 'http.request') {
      return mediumRisk(translateFn)
    }
    if (
      [
        'wallet.list',
        'wallet.balance.read',
        'wallet.create_invoice_public',
        'ext.storage.read_public',
        'payments.watch'
      ].includes(permission.id)
    ) {
      return mediumRisk(translateFn)
    }
    return lowRisk(translateFn)
  }

  function permissionRisk(permissions, extensions, translateFn) {
    const risks = permissions.map(permission =>
      permissionRiskForPermission(permission, extensions, translateFn)
    )
    const highestRisk = risks.find(risk => risk.level === 'high')
    if (highestRisk) return highestRisk
    return risks.find(risk => risk.level === 'medium') || lowRisk(translateFn)
  }

  function permissionOrderIndex(permissionId) {
    const order = [
      'wallet.pay_invoice',
      'wallet.list',
      'wallet.balance.read',
      'extension.api.request',
      'http.request',
      'ui.camera.scan_qr',
      'ext.storage.read',
      'ext.storage.write',
      'ext.storage.read_public',
      'wallet.create_invoice_public',
      'wallet.create_invoice',
      'utils.basic'
    ]
    const index = order.indexOf(permissionId)
    return index === -1 ? order.length : index
  }

  function publicStorageFieldGroups(permission) {
    const tables = permission.policies
    if (!Array.isArray(tables)) return []
    return tables
      .map(table => {
        const tableName =
          typeof table === 'string' ? table : table?.table_name || ''
        const fields =
          typeof table === 'string' || !Array.isArray(table?.public_fields)
            ? []
            : table.public_fields.filter(
                field => typeof field === 'string' && field
              )
        return tableName ? {table: tableName, fields} : null
      })
      .filter(Boolean)
  }

  function httpRequestPermissionHosts(permission) {
    const hosts = permission.policies
    if (!Array.isArray(hosts)) return []
    return hosts
      .map(host => (typeof host === 'string' ? host : host?.host || ''))
      .filter(host => typeof host === 'string' && host)
  }

  function publicInvoicePolicies(permission) {
    const policies = permission.policies
    if (!Array.isArray(policies)) return []
    return policies
      .map(policy => {
        if (!policy || typeof policy !== 'object') return null
        const table = policy.table
        const walletField = policy.wallet_field
        if (typeof table !== 'string' || !table) return null
        if (typeof walletField !== 'string' || !walletField) return null
        return {table, walletField}
      })
      .filter(Boolean)
  }

  function permissionDisplayItem(permissions, extensions, translateFn) {
    const permission = permissions[0]
    const isReadWriteStorage =
      permissions.length === 2 &&
      permissions.some(permission => permission.id === 'ext.storage.read') &&
      permissions.some(permission => permission.id === 'ext.storage.write')
    const descriptions = permissions
      .map(permission => permissionManifestDescription(permission))
      .filter(Boolean)
    const item = {
      id: isReadWriteStorage ? 'ext.storage.read_write' : permission.id,
      label: isReadWriteStorage
        ? translate(translateFn, 'extension_permission_ext_storage_read_write')
        : permissionLabel(permission, translateFn),
      risk: permissionRisk(permissions, extensions, translateFn),
      badges: [],
      descriptions,
      fieldGroups: [],
      invoicePolicies: [],
      extensionAccess: [],
      httpHosts: []
    }

    if (permission.id === 'ext.storage.read_public') {
      item.fieldGroups = publicStorageFieldGroups(permission)
      item.badges = item.fieldGroups.map(group => ({
        key: group.table,
        label: group.table
      }))
    }

    if (permission.id === 'extension.api.request') {
      item.extensionAccess = extensionApiPermissionTargets(
        permission,
        extensions
      )
      item.badges = item.extensionAccess.map(target => ({
        key: target.id,
        label: target.name
      }))
    }

    if (permission.id === 'http.request') {
      item.httpHosts = httpRequestPermissionHosts(permission)
    }

    if (permission.id === 'wallet.create_invoice_public') {
      item.invoicePolicies = publicInvoicePolicies(permission)
    }

    return item
  }

  function displayItems({permissions, extensions, translate}) {
    const permissionList = permissions || []
    const permissionsById = new Map(
      permissionList.map(permission => [permission.id, permission])
    )
    const hasReadWriteStorage =
      permissionsById.has('ext.storage.read') &&
      permissionsById.has('ext.storage.write')
    let addedReadWriteStorage = false

    return permissionList
      .map((permission, index) => {
        if (
          hasReadWriteStorage &&
          ['ext.storage.read', 'ext.storage.write'].includes(permission.id)
        ) {
          if (addedReadWriteStorage) return null
          addedReadWriteStorage = true
          return {
            index,
            orderId: 'ext.storage.read',
            permissions: [
              permissionsById.get('ext.storage.read'),
              permissionsById.get('ext.storage.write')
            ]
          }
        }
        return {
          index,
          orderId: permission.id,
          permissions: [permission]
        }
      })
      .filter(Boolean)
      .sort((left, right) => {
        const leftOrder = permissionOrderIndex(left.orderId)
        const rightOrder = permissionOrderIndex(right.orderId)
        return leftOrder === rightOrder
          ? left.index - right.index
          : leftOrder - rightOrder
      })
      .map(group =>
        permissionDisplayItem(group.permissions, extensions || [], translate)
      )
  }

  window.LNbitsExtensionPermissions = {
    displayItems,
    hasHighRisk({permissions, extensions, translate}) {
      return displayItems({permissions, extensions, translate}).some(
        permission => permission.risk.level === 'high'
      )
    }
  }

  window.app.component('lnbits-extension-permissions', {
    template: '#lnbits-extension-permissions',
    props: {
      permissions: {
        type: Array,
        default: () => []
      },
      extensions: {
        type: Array,
        default: () => []
      }
    },
    computed: {
      displayItems() {
        return window.LNbitsExtensionPermissions.displayItems({
          permissions: this.permissions,
          extensions: this.extensions,
          translate: key => this.$t(key)
        })
      }
    },
    methods: {
      publicInvoicePolicySentence(policy) {
        return `Invoices will be created using ${policy.walletField} from ${policy.table}.`
      },
      permissionAccessLabel(access) {
        const key = `extension_permission_access_${access}`
        const label = this.$t(key)
        return label === key ? access : label
      }
    }
  })
})()
