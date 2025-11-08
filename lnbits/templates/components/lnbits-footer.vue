<template id="lnbits-footer">
  <q-footer
    v-if="showFooter"
    class="bg-transparent q-px-lg q-py-md"
    :class="{'text-dark': !$q.dark.isActive}"
  >
    <q-space class="q-py-lg lt-md"></q-space>
    <q-toolbar class="gt-sm">
      <q-toolbar-title class="text-caption">
        <span v-text="title"></span>
        <br />
        <small v-text="$t('lnbits_version') + ': ' + version"></small>
      </q-toolbar-title>
      <q-space></q-space>
      <q-btn
        flat
        dense
        :color="$q.dark.isActive ? 'white' : 'primary'"
        type="a"
        href="/docs"
        target="_blank"
        rel="noopener noreferrer"
      >
        <span v-text="$t('api_docs')"></span>
        <q-tooltip><span v-text="$t('view_swagger_docs')"></span></q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        :color="$q.dark.isActive ? 'white' : 'primary'"
        icon="code"
        type="a"
        href="https://github.com/lnbits/lnbits"
        target="_blank"
        rel="noopener noreferrer"
      >
        <q-tooltip><span v-text="$t('view_github')"></span></q-tooltip>
      </q-btn>
    </q-toolbar>
  </q-footer>
</template>
