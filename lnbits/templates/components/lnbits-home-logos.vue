<template id="lnbits-home-logos">
  <div v-if="showLogos" class="full-width">
    <div class="wrapper">
      <div class="marquee">
        <div class="marquee__group">
          <div v-for="logo in logos">
            <a :href="logo.url" target="_blank" rel="noopener noreferrer">
              <q-img
                contain
                :src="$q.dark.isActive ? logo.darkSrc : logo.lightSrc"
              ></q-img>
            </a>
          </div>
        </div>
        <!-- Duplicate for seamless looping -->
        <div class="marquee__group">
          <div v-for="logo in logos">
            <a :href="logo.url" target="_blank" rel="noopener noreferrer">
              <q-img
                contain
                :src="$q.dark.isActive ? logo.darkSrc : logo.lightSrc"
              ></q-img>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
