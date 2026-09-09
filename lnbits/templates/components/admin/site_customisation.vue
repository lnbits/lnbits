<template id="lnbits-admin-site-customisation">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm" v-text="$t('ui_default_theme')"></h6>
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-md-6">
        <q-select
          dense
          filled
          v-model="formData.lnbits_theme_options"
          multiple
          :hint="$t('themes_hint')"
          :options="lnbits_theme_options"
          :label="$t('themes')"
        ></q-select>
      </div>
      <div class="col-12 col-md-6">
        <q-select
          dense
          filled
          v-model="formData.lnbits_default_theme"
          :options="lnbits_theme_options"
          label="Theme"
          @update:model-value="applyGlobalTheme"
        ></q-select>
      </div>
      <div class="col-12 col-md-4">
        <q-select
          dense
          filled
          v-model="formData.lnbits_default_border"
          :options="globalBorderOptions"
          label="Border"
          @update:model-value="applyGlobalBorder"
        ></q-select>
      </div>
      <div class="col-12 col-md-4">
        <q-select
          dense
          filled
          v-model="formData.lnbits_default_reaction"
          :options="reactionOptions"
          label="Payment reaction"
          @update:model-value="applyGlobalReaction"
        ></q-select>
      </div>
      <div class="col-12 col-md-4">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_default_bgimage"
          label="Background Image"
          hint="This must be a trusted source. It can change the content and it can log your IP address."
        >
          <template v-slot:append>
            <q-btn
              dense
              flat
              round
              icon="upload"
              @click="$refs.adminBackgroundImageInput.click()"
            >
              <q-tooltip>Upload background image</q-tooltip>
            </q-btn>
          </template>
        </q-input>
        <input
          type="file"
          ref="adminBackgroundImageInput"
          accept="image/*"
          style="display: none"
          @change="onBackgroundImageInput"
        />
      </div>
    </div>
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_gradient"
          color="primary"
          :label="$t('gradient_background')"
        ></q-toggle>
      </div>
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_dark"
          color="primary"
          :label="$t('toggle_darkmode')"
        ></q-toggle>
      </div>
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_card_rounded"
          color="primary"
          :label="$t('rounded_ui')"
        ></q-toggle>
      </div>
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_card_gradient"
          color="primary"
          :label="$t('card_gradient')"
        ></q-toggle>
      </div>
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_card_shadow"
          color="primary"
          :label="$t('card_shadow')"
        ></q-toggle>
      </div>
      <div class="col-12 col-sm-6 col-lg-4">
        <q-toggle
          type="bool"
          v-model="formData.lnbits_default_burger_menu_background"
          color="primary"
          :label="$t('burger_menu_background')"
        ></q-toggle>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <h6 class="q-my-none q-mb-sm">Site Identity</h6>
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-md-6">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_site_title"
          :label="
            $t('ui_site_title') + $t('ui_changing_remove_lnbits_elements')
          "
        ></q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_site_tagline"
          :label="$t('ui_site_tagline')"
        ></q-input>
      </div>
      <div class="col-12">
        <q-input
          dense
          v-model="formData.lnbits_site_description"
          filled
          type="textarea"
          :label="$t('ui_site_description')"
          :hint="$t('ui_site_description_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-4">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_custom_logo"
          :label="$t('custom_logo')"
          :hint="$t('custom_logo_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-4">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_qr_logo"
          :label="$t('ui_qr_code_logo')"
          :hint="$t('ui_qr_code_logo_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-4">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_apple_touch_icon"
          :label="$t('ui_apple_touch_icon')"
          :hint="$t('ui_apple_touch_icon_hint')"
        ></q-input>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <h6 class="q-my-none q-mb-sm">Home Page</h6>
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12">
        <q-toggle
          :tip="$t('ui_toggle_elements_tip')"
          v-model="formData.lnbits_show_home_page_elements"
          :label="
            formData.lnbits_show_home_page_elements
              ? $t('ui_elements_enable')
              : $t('ui_elements_disable')
          "
        ></q-toggle>
      </div>
      <div class="col-12">
        <div class="text-subtitle1" v-text="$t('ui_custom_badge_title')"></div>
        <p class="q-mb-none" v-text="$t('ui_custom_badge_desc')"></p>
      </div>
      <div class="col-12 col-md-6">
        <q-input
          dense
          filled
          type="text"
          tip="Custom Badge"
          v-model.trim="formData.lnbits_custom_badge"
          :label="$t('ui_custom_badge')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6">
        <q-select
          dense
          filled
          v-model="formData.lnbits_custom_badge_color"
          :options="colors"
          :label="$t('ui_custom_badge_color_label')"
        ></q-select>
      </div>
      <div class="col-12">
        <q-input
          dense
          filled
          type="text"
          tip="Custom Image"
          v-model.trim="formData.lnbits_custom_image"
          :label="$t('ui_custom_image_label')"
          :hint="$t('ui_custom_image_hint')"
        ></q-input>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <h6 class="q-my-none q-mb-sm">Wallet Experience</h6>
    <div class="row q-col-gutter-md q-mb-md">
      <div class="col-12 col-md-6 col-lg-3">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_default_wallet_name"
          :label="$t('ui_default_wallet_name')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-3">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_wallet_featured_button_label"
          :label="$t('wallet_featured_button_label')"
          :hint="$t('wallet_featured_button_label_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-3">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_wallet_featured_button_url"
          :label="$t('wallet_featured_button_url')"
          :hint="$t('wallet_featured_button_url_hint')"
        ></q-input>
      </div>
      <div class="col-12 col-md-6 col-lg-3">
        <q-input
          dense
          filled
          type="text"
          v-model="formData.lnbits_wallet_featured_button_icon"
          label="bolt"
          :hint="$t('wallet_featured_button_icon_hint')"
        ></q-input>
      </div>
    </div>

    <q-separator class="q-mb-lg q-mt-md"></q-separator>
    <q-expansion-item
      icon="campaign"
      :label="$t('ad_space_section_title')"
      :caption="`${$t('advanced')} · ${$t('ad_space_section_desc')}`"
    >
      <q-card-section class="row q-col-gutter-lg">
        <div class="col-12">
          <q-toggle
            v-model="formData.lnbits_ad_space_enabled"
            :label="
              formData.lnbits_ad_space_enabled
                ? $t('ads_enabled')
                : $t('ads_disabled')
            "
          ></q-toggle>
        </div>
        <div class="col-12 col-md-6">
          <q-input
            dense
            filled
            type="text"
            v-model="formData.lnbits_ad_space_title"
            :label="$t('ad_space_title')"
            :hint="$t('ad_space_title_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-6">
          <q-input
            dense
            filled
            v-model="formData.lnbits_ad_space"
            type="text"
            :label="$t('ad_slots')"
            :hint="$t('ad_slots_hint')"
          >
            <q-tooltip>
              format {url};{img-light};{img-dark},{url};{img-light};{img-dark}"
            </q-tooltip>
          </q-input>
        </div>
      </q-card-section>
    </q-expansion-item>
  </q-card-section>
</template>
