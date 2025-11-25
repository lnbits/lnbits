<template id="lnbits-wallet-share">
  <q-expansion-item
    v-if="g.wallet.walletType == 'lightning'"
    group="extras"
    icon="share"
    :label="$t('share_wallet')"
  >
    <template v-slot:header>
      <q-item-section avatar>
        <q-avatar icon="share" style="margin-left: -5px" />
      </q-item-section>

      <q-item-section>
        <span v-text="$t('share_wallet')"></span>
      </q-item-section>

      <q-item-section side v-if="walletPendingRequests.length">
        <div class="row items-center">
          <q-icon name="hail" color="secondary" size="24px" />
          <span v-text="walletPendingRequests.length"></span>
        </div>
      </q-item-section>
    </template>
    <q-card>
      <q-card-section>
        You can invite other users to have access to this wallet.
        <br />
        The access is limitted by the permission you grant.
      </q-card-section>

      <q-card-section>
        <div class="row">
          <div class="col-5">
            <q-input
              v-model="walletShareInvite.username"
              @keyup.enter="inviteUserToWallet()"
              label="Username"
              hint="Invite user to this wallet"
              dense
            >
            </q-input>
          </div>
          <div class="col-6">
            <q-select
              :options="permissionOptions"
              v-model="walletShareInvite.permissions"
              emit-value
              map-options
              multiple
              use-chips
              dense
              class="q-pl-md"
              hint="Select permissions for this user"
            ></q-select>
          </div>
          <div class="col-1">
            <q-btn
              @click="inviteUserToWallet()"
              dense
              flat
              icon="person_add_alt"
              class="float-right"
            ></q-btn>
          </div>
        </div>
      </q-card-section>
      <q-separator class="q-mt-lg"></q-separator>
      <q-expansion-item
        group="wallet_shares"
        dense
        expand-separator
        icon="share"
        :label="'Shared With (' + walletApprovedShares.length + ')'"
      >
        <q-card>
          <q-card-section v-if="walletApprovedShares.length">
            <div v-for="share in walletApprovedShares" class="row q-mb-xs">
              <div class="col-3 q-mt-md">
                <strong v-text="share.username"></strong>
              </div>
              <div class="col-1 q-mt-sm">
                <q-icon v-if="share.comment" name="add_comment">
                  <q-tooltip v-text="share.comment"></q-tooltip>
                </q-icon>
              </div>
              <div class="col-6">
                <q-select
                  v-model="share.permissions"
                  :options="permissionOptions"
                  emit-value
                  map-options
                  multiple
                  use-chips
                  dense
                ></q-select>
              </div>
              <div class="col-1 q-mt-sm">
                <q-btn
                  flat
                  color="red"
                  icon="delete"
                  outline
                  class="full-width"
                  @click="deleteSharePermission(share)"
                ></q-btn>
              </div>
              <div class="col-1 q-mt-sm">
                <q-btn
                  dense
                  flat
                  color="primary"
                  icon="check"
                  class="full-width"
                  @click="updateSharePermissions(share)"
                ></q-btn>
              </div>
            </div>
          </q-card-section>
          <q-card-section v-else>
            <span>This wallet is not shared with anyone.</span>
          </q-card-section>
        </q-card>
      </q-expansion-item>
      <q-expansion-item
        group="wallet_shares"
        dense
        expand-separator
        icon="group_add"
        :label="'Pending Invitations (' + walletPendingInvites.length + ')'"
      >
        <q-card>
          <q-card-section v-if="walletPendingInvites.length">
            <div v-for="share in walletPendingInvites" class="row q-mb-xs">
              <div class="col-3 q-mt-md">
                <strong v-text="share.username"></strong>
              </div>

              <div class="col-8">
                <q-select
                  v-model="share.permissions"
                  :options="permissionOptions"
                  emit-value
                  map-options
                  multiple
                  use-chips
                  dense
                ></q-select>
              </div>
              <div class="col-1 q-mt-sm">
                <q-btn
                  flat
                  color="red"
                  icon="delete"
                  outline
                  class="full-width"
                  @click="deleteSharePermission(share)"
                ></q-btn>
              </div>
            </div>
          </q-card-section>

          <q-card-section v-else>
            <span>No pending invites.</span>
          </q-card-section>
        </q-card>
      </q-expansion-item>

      <q-card-section> </q-card-section>
    </q-card>
  </q-expansion-item>
  <q-expansion-item
    v-else-if="g.wallet.walletType == 'lightning-shared'"
    group="extras"
    icon="supervisor_account"
    :label="$t('shared_wallet')"
  >
    <q-card>
      <q-card-section>
        This wallet does not belong to you. It is a shared Lightning wallet.
        <br />
        The owner can revoke the permissions at any moment.
      </q-card-section>
      <q-card-section>
        <q-item dense class="q-pa-none">
          <q-item-section>
            <q-item-label>
              <strong>Shared Wallet ID: </strong
              ><em
                v-text="
                  walletIdHidden ? '****************' : g.wallet.sharedWalletId
                "
              ></em>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div>
              <q-icon
                :name="walletIdHidden ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="walletIdHidden = !walletIdHidden"
              ></q-icon>
              <q-icon
                name="content_copy"
                class="cursor-pointer q-ml-sm"
                @click="utils.copyText(g.wallet.sharedWalletId)"
              ></q-icon>
              <q-icon name="qr_code" class="cursor-pointer q-ml-sm">
                <q-popup-proxy>
                  <div class="q-pa-md">
                    <lnbits-qrcode
                      :value="g.wallet.sharedWalletId"
                      :show-buttons="false"
                    ></lnbits-qrcode>
                  </div>
                </q-popup-proxy>
              </q-icon>
            </div>
          </q-item-section>
        </q-item>
      </q-card-section>
      <q-card-section>
        <div class="row">
          <div class="col-3 q-mt-md">
            <strong>Permissions:</strong>
          </div>
          <div class="col-9">
            <q-select
              v-model="g.wallet.sharePermissions"
              :options="permissionOptions"
              emit-value
              map-options
              multiple
              use-chips
              dense
              disable
            ></q-select>
          </div>
        </div>
      </q-card-section>
    </q-card>
  </q-expansion-item>
  <q-expansion-item
    v-else
    group="extras"
    icon="question_mark"
    :label="$t('share_wallet')"
  >
    <q-card>
      <q-card-section>
        Unknown wallet type:
        <strong v-text="g.wallet.walletType" class="q-ml-md"></strong>
      </q-card-section>
    </q-card>
  </q-expansion-item>
</template>
