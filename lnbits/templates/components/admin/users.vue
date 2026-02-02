<template id="lnbits-admin-users">
  <q-card-section class="q-pa-none">
    <h6 class="q-my-none q-mb-sm">
      <span v-text="$t('user_management')"></span>
    </h6>

    <div class="row">
      <div class="col-12 col-md-6 q-pr-sm">
        <p><span v-text="$t('admin_users')"></span></p>
        <q-input
          filled
          v-model="formAddAdmin"
          @keydown.enter="addAdminUser"
          type="text"
          :label="$t('admin_users_label')"
          :hint="$t('admin_users_hint')"
        >
          <q-btn @click="addAdminUser" dense flat icon="add"></q-btn>
        </q-input>
        <div>
          <q-chip
            v-for="user in formData.lnbits_admin_users"
            :key="user"
            removable
            @remove="removeAdminUser(user)"
            color="primary"
            text-color="white"
            :label="user"
            class="ellipsis"
          >
          </q-chip>
        </div>
      </div>
      <div class="col-12 col-md-6">
        <p><span v-text="$t('allowed_users')"></span></p>
        <q-input
          filled
          v-model="formAddUser"
          @keydown.enter="addAllowedUser"
          type="text"
          :label="$t('allowed_users_label')"
          :hint="$t('allowed_users_hint')"
        >
          <q-btn @click="addAllowedUser" dense flat icon="add"></q-btn>
        </q-input>
        <div>
          <q-chip
            v-for="user in formData.lnbits_allowed_users"
            :key="user"
            removable
            @remove="removeAllowedUser(user)"
            color="primary"
            text-color="white"
            :label="user"
            class="ellipsis"
          >
          </q-chip>
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-12 col-md-6 q-mt-sm">
        <q-item tag="label" v-ripple>
          <q-item-section>
            <q-item-label v-text="$t('allow_creation_user')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('allow_creation_user_desc')"
            ></q-item-label>
          </q-item-section>
          <q-item-section avatar>
            <q-toggle
              size="md"
              v-model="formData.lnbits_allow_new_accounts"
              checked-icon="check"
              color="green"
              unchecked-icon="clear"
            />
          </q-item-section>
        </q-item>
      </div>
      <div class="col-12 col-md-6 q-mt-sm">
        <q-item tag="label" v-ripple>
          <q-item-section>
            <q-item-label v-text="$t('require_user_activation')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('require_user_activation_desc')"
            ></q-item-label>
          </q-item-section>
          <q-item-section avatar>
            <q-toggle
              size="md"
              v-model="formData.lnbits_require_user_activation"
              checked-icon="check"
              color="green"
              unchecked-icon="clear"
            />
          </q-item-section>
        </q-item>
      </div>
    </div>
  </q-card-section>
  <div v-if="formData.lnbits_require_user_activation" class="row">
    <div class="col">
      <q-list bordered class="rounded-borders">
        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-icon name="confirmation_number" size="md"></q-icon>
            </q-item-section>

            <q-item-section> Invitation Code </q-item-section>

            <q-item-section side>
              <div class="row items-center">
                <q-toggle
                  size="md"
                  :label="$t('enabled')"
                  v-model="formData.lnbits_user_activation_by_invitation_code"
                  color="green"
                  unchecked-icon="clear"
                />
              </div>
            </q-item-section>
          </template>

          <q-card class="q-pb-xl">
            <q-card-section>
              <div
                class="q-my-md q-pa-sm text-body2 text-grey-4 bg-grey-9 rounded-borders"
              >
                <q-icon
                  name="info"
                  color="orange-4"
                  size="18px"
                  class="q-mr-xs"
                ></q-icon>
                Users will need to provide a valid invitation code during
                registration to activate their account.
              </div>
            </q-card-section>
            <q-card-section>
              <div class="row">
                <div class="col-12 col-md-6 q-pr-sm">
                  <p><span v-text="$t('reusable_activation_code')"></span></p>
                  <q-input
                    filled
                    v-model="formData.lnbits_register_reusable_activation_code"
                    :type="showReusableActivationCode ? 'text' : 'password'"
                    :label="$t('reusable_activation_code_label')"
                    :hint="$t('reusable_activation_code_hint')"
                  >
                    <q-btn
                      @click="
                        showReusableActivationCode = !showReusableActivationCode
                      "
                      dense
                      flat
                      :icon="
                        showReusableActivationCode
                          ? 'visibility_off'
                          : 'visibility'
                      "
                      color="grey"
                    ></q-btn>
                    <q-btn
                      @click="
                        utils.copyText(
                          formData.lnbits_register_reusable_activation_code
                        )
                      "
                      dense
                      flat
                      icon="content_copy"
                      color="grey"
                    ></q-btn>
                  </q-input>
                </div>
                <div class="col-12 col-md-6">
                  <p><span v-text="$t('one_time_activation_code')"></span></p>
                  <q-input
                    filled
                    v-model="formAddActivationCode"
                    @keydown.enter="addOneTimeActivationCode"
                    type="text"
                    :label="$t('one_time_activation_code_label')"
                    :hint="$t('one_time_activation_code_hint')"
                  >
                    <q-btn
                      @click="addOneTimeActivationCode"
                      dense
                      flat
                      icon="add"
                    ></q-btn>
                  </q-input>
                  <div>
                    <q-chip
                      v-for="code in formData.lnbits_register_one_time_activation_codes"
                      :key="code"
                      removable
                      @remove="removeOneTimeActivationCode(code)"
                      color="primary"
                      text-color="white"
                      :label="code"
                      class="ellipsis"
                    >
                    </q-chip>
                  </div>
                </div>
              </div>
            </q-card-section>
          </q-card>
        </q-expansion-item>
        <q-separator></q-separator>

        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-avatar>
                <q-icon name="bolt" size="md"></q-icon>
              </q-avatar>
            </q-item-section>

            <q-item-section> Payment </q-item-section>

            <q-item-section side>
              <div class="row items-center">
                <q-toggle
                  size="md"
                  :label="$t('enabled')"
                  v-model="formData.lnbits_user_activation_by_payment"
                  color="green"
                  unchecked-icon="clear"
                />
              </div>
            </q-item-section>
          </template>

          <q-card class="q-pb-xl"> qqq </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-avatar>
                <q-img
                  src="/static/images/logos/nostr.svg"
                  class="bg-primary"
                ></q-img>
              </q-avatar>
            </q-item-section>

            <q-item-section> Nostr </q-item-section>

            <q-item-section side>
              <div class="row items-center">
                <q-toggle
                  size="md"
                  :label="$t('enabled')"
                  v-model="formData.lnbits_user_activation_by_nostr"
                  color="green"
                  unchecked-icon="clear"
                />
              </div>
            </q-item-section>
          </template>

          <q-card class="q-pb-xl"> wwww </q-card>
        </q-expansion-item>
        <q-separator></q-separator>
        <q-expansion-item header-class="text-primary text-bold">
          <template v-slot:header>
            <q-item-section avatar>
              <q-avatar>
                <q-icon name="email"></q-icon>
              </q-avatar>
            </q-item-section>

            <q-item-section> Email </q-item-section>

            <q-item-section side>
              <div class="row items-center">
                <q-toggle
                  size="md"
                  :label="$t('enabled')"
                  v-model="formData.lnbits_user_activation_by_email"
                  color="green"
                  unchecked-icon="clear"
                />
              </div>
            </q-item-section>
          </template>

          <q-card class="q-pb-xl"> xxxx </q-card>
        </q-expansion-item>
      </q-list>
    </div>
  </div>
</template>
