<template id="lnbits-admin-site-customisation">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none">
      <span v-text="$t('ui_management')"></span>
    </h6>
    <br />
    <div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_site_title"
            :label="
              $t('ui_site_title') + $t('ui_changing_remove_lnbits_elements')
            "
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_site_tagline"
            :label="$t('ui_site_tagline')"
          ></q-input>
          <br />
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-12">
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
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12">
          <q-input
            v-model="formData.lnbits_site_description"
            filled
            type="textarea"
            :label="$t('ui_site_description')"
            :hint="$t('ui_site_description_hint')"
          />
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_default_wallet_name"
            :label="$t('ui_default_wallet_name')"
          ></q-input>
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_qr_logo"
            :label="$t('ui_qr_code_logo')"
            :hint="$t('ui_qr_code_logo_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_apple_touch_icon"
            :label="$t('ui_apple_touch_icon')"
            :hint="$t('ui_apple_touch_icon_hint')"
          ></q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-12">
          <p><span v-text="$t('wallet_featured_button_title')"></span></p>
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_wallet_featured_button_label"
            :label="$t('wallet_featured_button_label')"
            :hint="$t('wallet_featured_button_label_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_wallet_featured_button_url"
            :label="$t('wallet_featured_button_url')"
            :hint="$t('wallet_featured_button_url_hint')"
          ></q-input>
        </div>
        <div class="col-12 col-md-4">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_wallet_featured_button_icon"
            label="bolt"
            :hint="$t('wallet_featured_button_icon_hint')"
          ></q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md q-mt-md">
        <div class="col-12 col-md-12">
          <h6 class="q-my-sm">
            <span v-text="$t('ui_custom_badge_title')"></span>
          </h6>
          <p class="q-mb-none">
            <span v-text="$t('ui_custom_badge_desc')"></span>
          </p>
        </div>
        <div class="col-12">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6">
              <q-input
                filled
                type="text"
                tip="Custom Badge"
                v-model.trim="formData.lnbits_custom_badge"
                :label="$t('ui_custom_badge')"
              ></q-input>
            </div>
            <div class="col-12 col-md-6">
              <q-select
                filled
                v-model="formData.lnbits_custom_badge_color"
                :options="colors"
                :label="$t('ui_custom_badge_color_label')"
              ></q-select>
            </div>
          </div>
        </div>
        <div class="col-12">
          <h6 class="q-my-sm"><span v-text="$t('ui_custom_image')"></span></h6>
          <q-input
            filled
            type="text"
            tip="Custom Image"
            v-model.trim="formData.lnbits_custom_image"
            :label="$t('ui_custom_image_label')"
            :hint="$t('ui_custom_image_hint')"
          ></q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-select
            filled
            v-model="formData.lnbits_theme_options"
            multiple
            :hint="$t('themes_hint')"
            :options="lnbits_theme_options"
            :label="$t('themes')"
          ></q-select>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_custom_logo"
            :label="$t('custom_logo')"
            :hint="$t('custom_logo_hint')"
          ></q-input>
          <br />
        </div>
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-12">
          <h6 class="q-my-sm">
            <span v-text="$t('ad_space_section_title')"></span>
          </h6>
          <p class="q-my-none">
            <span v-text="$t('ad_space_section_desc')"></span>
          </p>
        </div>
        <div class="col-12 col-md-12">
          <q-toggle
            v-model="formData.lnbits_ad_space_enabled"
            :label="
              formData.lnbits_ad_space_enabled
                ? $t('ads_enabled')
                : $t('ads_disabled')
            "
          />
        </div>
        <div class="col-12 col-md-6">
          <q-input
            filled
            type="text"
            v-model="formData.lnbits_ad_space_title"
            :label="$t('ad_space_title')"
            :hint="$t('ad_space_title_hint')"
          ></q-input>
          <br />
        </div>
        <div class="col-12 col-md-6">
          <q-input
            class="q-mb-md"
            filled
            v-model="formData.lnbits_ad_space"
            type="text"
            :label="$t('ad_slots')"
            :hint="$t('ad_slots_hint')"
            ><q-tooltip>
              format {url};{img-light};{img-dark},{url};{img-light};{img-dark}"
            </q-tooltip>
          </q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md q-my-md">
        <div class="col-12" v-text="$t('ui_default_theme')"></div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-select
            v-model="formData.lnbits_default_border"
            :options="globalBorderOptions"
            label="Border"
            @update:model-value="applyGlobalBorder"
          >
          </q-select>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-select
            v-model="formData.lnbits_default_theme"
            :options="lnbits_theme_options"
            label="Theme"
            @update:model-value="applyGlobalTheme"
          >
          </q-select>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-select
            v-model="formData.lnbits_default_reaction"
            :options="reactionOptions"
            label="Payment reaction"
            @update:model-value="applyGlobalReaction"
          >
          </q-select>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-input
            type="text"
            v-model="formData.lnbits_default_bgimage"
            label="Background Image"
            @update:model-value="applyGlobalBgimage"
            hint="This must be a trusted source. It can change the content and it can log your IP address."
          >
          </q-input>
        </div>
      </div>
      <div class="row q-col-gutter-md q-mb-md">
        <div class="col-12 col-sm-6 col-lg-2">
          <q-toggle
            type="bool"
            v-model="formData.lnbits_default_gradient"
            color="primary"
            :label="$t('gradient_background')"
          >
          </q-toggle>
        </div>
        <div class="col-12 col-sm-6 col-lg-2">
          <q-toggle
            type="bool"
            v-model="formData.lnbits_default_dark"
            color="primary"
            :label="$t('toggle_darkmode')"
          >
          </q-toggle>
        </div>
        <div class="col-12 col-sm-6 col-lg-2">
          <q-toggle
            type="bool"
            v-model="formData.lnbits_default_card_rounded"
            color="primary"
            :label="$t('rounded_ui')"
          >
          </q-toggle>
        </div>
        <div class="col-12 col-sm-6 col-lg-2">
          <q-toggle
            type="bool"
            v-model="formData.lnbits_default_card_gradient"
            color="primary"
            :label="$t('card_gradient')"
          >
          </q-toggle>
        </div>
        <div class="col-12 col-sm-6 col-lg-2">
          <q-toggle
            type="bool"
            v-model="formData.lnbits_default_card_shadow"
            color="primary"
            :label="$t('card_shadow')"
          >
          </q-toggle>
        </div>
      </div>
    </div>
  </q-card-section>
</template>
