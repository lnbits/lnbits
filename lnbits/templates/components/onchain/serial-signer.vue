<template id="onchain-serial-signer">
  <div>
    <q-btn-dropdown
      split
      unelevated
      color="primary"
      icon="usb"
      label="Serial device"
      :text-color="
        connected ? (hww.authenticated ? 'green' : 'orange') : 'white'
      "
      :loading="isConnecting"
      :disable="closingSerialPort"
      @click="openSerialPortDialog"
    >
      <q-list>
        <q-item
          v-if="connected && !hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowPasswordDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.login')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.enter_password_hww')">
            </q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwLogout()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.logout')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.clear_password_hww')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="!selectedPort"
          clickable
          v-close-popup
          @click="openSerialPortConfig"
        >
          <q-item-section>
            <q-item-label
              v-text="$t('onchain.config_and_connect')"
            ></q-item-label>
            <q-item-label caption v-text="$t('onchain.set_serial_port_params')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          clickable
          v-close-popup
          @click="closeSerialPort()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.disconnect')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.disconnect_from_serial')"
            ></q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="connected"
          clickable
          v-close-popup
          @click="hwwShowRestoreDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.restore')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.restore_wallet_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowSeed()"
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.show_seed')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.show_seed_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="connected"
          @click="hwwShowWipeDialog()"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.wipe')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.wipe_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="connected"
          :disable="
            trng.running || hww.loggingIn || hww.sendingPsbt || hww.signingPsbt
          "
          @click="hwwTestTrng()"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.trng_check')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.trng_check_desc')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="connected" @click="hwwHelp()" clickable v-close-popup>
          <q-item-section>
            <q-item-label v-text="$t('onchain.help')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('onchain.view_commands')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          @click="showConsole = true"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('onchain.console')"></q-item-label>
            <q-item-label caption v-text="$t('onchain.serial_comm_messages')">
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-btn-dropdown>

    <q-dialog
      v-model="trng.showDialog"
      :persistent="trng.running"
      position="top"
    >
      <q-card class="q-pa-lg lnbits__dialog-card">
        <div class="text-h6 q-mb-md" v-text="$t('onchain.trng_result')"></div>
        <div v-if="trng.running" class="row items-center q-gutter-sm">
          <q-spinner color="primary" size="2em"></q-spinner>
          <span v-text="$t('onchain.trng_running')"></span>
        </div>
        <template v-else-if="trng.result">
          <q-banner
            :class="
              trng.result.looksHealthy
                ? 'bg-positive text-white'
                : 'bg-warning text-black'
            "
          >
            <span
              v-text="
                $t(
                  trng.result.looksHealthy
                    ? 'onchain.trng_healthy'
                    : 'onchain.trng_unexpected'
                )
              "
            ></span>
          </q-banner>
          <div class="q-markup-table q-my-md bg-transparent">
            <table class="q-table">
              <tbody>
                <tr>
                  <td v-text="$t('onchain.trng_samples')"></td>
                  <td v-text="trng.result.samples"></td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_expected')"></td>
                  <td>50</td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_range')"></td>
                  <td
                    v-text="
                      trng.result.minimumCount + '–' + trng.result.maximumCount
                    "
                  ></td>
                </tr>
                <tr>
                  <td v-text="$t('onchain.trng_chi_squared')"></td>
                  <td v-text="trng.result.chiSquared.toFixed(2)"></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="text-weight-bold" v-text="$t('onchain.trng_interval')"></p>
          <p v-text="$t('onchain.trng_thresholds')"></p>
          <p v-text="$t('onchain.trng_limit')"></p>
          <p v-text="$t('onchain.trng_continue')"></p>
        </template>
        <template v-else-if="trng.error">
          <q-banner class="bg-warning text-black">
            <span v-text="$t('onchain.trng_failed')"></span>
            <div v-text="trng.error"></div>
          </q-banner>
          <p class="q-mt-md" v-text="$t('onchain.trng_firmware')"></p>
        </template>
        <div class="row justify-end q-mt-md">
          <q-btn
            v-close-popup
            flat
            color="grey"
            :disable="trng.running"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showConfigDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwConfigAndConnect" class="q-gutter-md">
          <span v-text="$t('onchain.enter_config')"></span>
          <onchain-serial-port-config
            ref="serialPortConfig"
            :config="config"
          ></onchain-serial-port-config>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              type="submit"
              :label="$t('onchain.connect')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showPasswordDialog"
      :persistent="hww.loggingIn"
      @hide="passwordDialogClosed"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwLogin" class="q-gutter-md">
          <span v-text="$t('onchain.enter_password_hww_full')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('onchain.password')"
          ></q-input>
          <q-separator></q-separator>
          <q-toggle
            :label="$t('onchain.passphrase_optional')"
            color="primary"
            v-model="hww.hasPassphrase"
          ></q-toggle>
          <q-input
            v-if="hww.hasPassphrase"
            v-model="hww.passphrase"
            filled
            :type="hww.showPassphrase ? 'text' : 'password'"
            dense
            :label="$t('onchain.passphrase')"
            :hint="$t('onchain.passphrase_hint')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassphrase ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassphrase = !hww.showPassphrase"
              ></q-icon>
            </template>
          </q-input>

          <br />

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="!connected"
              :loading="hww.loggingIn"
              type="submit"
              :label="$t('onchain.login')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.loggingIn"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showConfirmationDialog" persistent position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <div class="q-gutter-md">
          <div
            v-if="tx && ['output', 'fee', 'sign'].includes(hww.confirm.stage)"
          >
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-12">
                <span class="text-subtitle2"
                  >Output <span v-text="hww.confirm.outputIndex + 1"></span
                ></span>
                <q-badge
                  v-if="tx.outputs[hww.confirm.outputIndex].branch_index === 1"
                  color="orange"
                  text-color="black"
                >
                  <span v-text="$t('onchain.change')"></span>
                </q-badge>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.address_colon')"></span>
              </div>
              <div class="col-9">
                <span
                  class="text-wrap"
                  v-text="tx.outputs[hww.confirm.outputIndex].address"
                ></span>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.amount_label')"></span>
              </div>
              <div class="col-9">
                <span
                  v-text="satBtc(tx.outputs[hww.confirm.outputIndex].amount)"
                ></span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.fee_label')"></span>
              </div>
              <div class="col-9">
                <span v-text="satBtc(tx.feeValue)"></span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('onchain.fee_rate_label')"></span>
              </div>
              <div class="col-9">
                <span><span v-text="tx.feeRate"></span> sats/vbyte</span>
              </div>
            </div>
          </div>
          <div class="row q-mt-lg">
            <div class="col-12">
              <q-badge class="text-subtitle2" color="yellow" text-color="black">
                <span v-text="$t('onchain.bowser_review_on_device')"></span>
              </q-badge>
            </div>
          </div>
          <div class="row items-center q-gutter-sm q-mt-lg" role="status">
            <q-spinner color="primary"></q-spinner>
            <span
              v-text="
                hww.confirm.stage === 'transfer'
                  ? $t('onchain.bowser_transfer')
                  : $t('onchain.bowser_physical_review')
              "
            ></span>
          </div>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showWipeDialog"
      :persistent="hww.settingUp"
      @hide="clearSetupSecrets"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwWipe" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('onchain.wipe_warning')"
          >
          </q-badge>
          <span v-text="$t('onchain.enter_new_password_hww')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('onchain.password')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('onchain.confirm_password')"
          ></q-input>
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('onchain.irreversible_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :loading="hww.settingUp"
              :disable="
                hww.settingUp ||
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              :label="$t('onchain.wipe')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.settingUp"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.console')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <div class="row q-mt-lg q-mb-lg">
          <div class="col">
            <q-badge
              class="text-subtitle2 float-right"
              color="yellow"
              text-color="black"
              v-text="$t('onchain.open_dev_console_warning')"
            >
            </q-badge>
          </div>
        </div>

        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('onchain.console')"
        ></q-input>
        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            :label="$t('onchain.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showSeedDialog"
      @hide="closeSeedDialog"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl">
        <span
          v-text="
            $t('onchain.check_word_position', {
              position: hww.seedWordPosition
            })
          "
        ></span>
        <p class="q-mt-lg" v-text="$t('onchain.bowser_seed_display')"></p>

        <div class="row q-mt-lg">
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 1"
              unelevated
              color="primary"
              @click="showPrevSeedWord"
              :disable="hww.seedLoading"
              :label="$t('onchain.prev')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 24"
              unelevated
              color="primary"
              @click="showNextSeedWord"
              :disable="hww.seedLoading"
              :label="$t('onchain.next')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.close')"
            ></q-btn>
          </div>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showRestoreDialog"
      :persistent="hww.settingUp"
      @hide="clearSetupSecrets"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwRestore" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('onchain.test_only_warning')"
          >
          </q-badge>
          <br />
          <q-toggle
            :label="$t('onchain.enter_word_list_space')"
            color="primary"
            v-model="hww.quickMnemonicInput"
          ></q-toggle>
          <br />

          <div v-if="hww.quickMnemonicInput">
            <q-input
              v-model.trim="hww.mnemonic"
              filled
              :type="hww.showMnemonic ? 'text' : 'password'"
              dense
              :label="$t('onchain.word_list')"
            >
              <template v-slot:append>
                <q-icon
                  :name="hww.showMnemonic ? 'visibility' : 'visibility_off'"
                  class="cursor-pointer"
                  @click="hww.showMnemonic = !hww.showMnemonic"
                ></q-icon>
              </template>
            </q-input>
          </div>

          <onchain-seed-input
            v-else
            @on-seed-input-done="seedInputDone"
          ></onchain-seed-input>
          <br />
          <q-separator></q-separator>
          <br />
          <span v-text="$t('onchain.enter_new_password_short')"></span>
          <q-input
            v-model.trim="hww.password"
            filled
            :type="hww.showPassword ? 'text' : 'password'"
            dense
            :label="$t('onchain.new_password')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassword ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassword = !hww.showPassword"
              ></q-icon>
            </template>
          </q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('onchain.confirm_password')"
          ></q-input>
          <br />
          <q-separator></q-separator>
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('onchain.all_data_lost_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :loading="hww.settingUp"
              :disable="
                hww.settingUp ||
                !hww.mnemonic ||
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              :label="$t('onchain.restore')"
            ></q-btn>
            <q-btn
              v-close-popup
              :disable="hww.settingUp"
              flat
              color="grey"
              class="q-ml-auto"
              :label="$t('onchain.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>
