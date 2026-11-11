<!--
  Copyright (C) 2022 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <cv-grid fullWidth>
    <cv-row>
      <cv-column class="page-title">
        <h2>{{ $t("settings.title") }}</h2>
      </cv-column>
    </cv-row>
    <cv-row v-if="error.getConfiguration">
      <cv-column>
        <NsInlineNotification
          kind="error"
          :title="$t('action.get-configuration')"
          :description="error.getConfiguration"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <cv-tile light>
          <cv-form @submit.prevent="configureModule">
            <NsInlineNotification
              v-if="!isConfigured && !loading.getConfiguration"
              kind="info"
              :title="$t('settings.host_choose_title')"
              :description="$t('settings.host_choose_description')"
              :showCloseButton="false"
              class="maxwidth"
            />
            <cv-text-input
              :label="$t('settings.wazuh_fqdn')"
              placeholder="wazuh.example.org"
              v-model.trim="host"
              class="mg-bottom"
              :helper-text="hostHelperText"
              :invalid-message="$t(error.host)"
              :disabled="
                loading.getConfiguration ||
                loading.configureModule ||
                isHostLocked
              "
              ref="host"
            >
            </cv-text-input>
            <NsToggle
              value="letsEncrypt"
              :label="core.$t('apps_lets_encrypt.request_https_certificate')"
              v-model="isLetsEncryptEnabled"
              :disabled="stillLoading"
              class="mg-bottom"
            >
              <template #tooltip>
                <div class="mg-bottom-sm">
                  {{ core.$t("apps_lets_encrypt.lets_encrypt_tips") }}
                </div>
                <div class="mg-bottom-sm">
                  <cv-link @click="goToCertificates">
                    {{ core.$t("apps_lets_encrypt.go_to_tls_certificates") }}
                  </cv-link>
                </div>
              </template>
              <template slot="text-left">{{
                $t("settings.disabled")
              }}</template>
              <template slot="text-right">{{
                $t("settings.enabled")
              }}</template>
            </NsToggle>
            <cv-row
              v-if="isLetsEncryptCurrentlyEnabled && !isLetsEncryptEnabled"
            >
              <cv-column>
                <NsInlineNotification
                  kind="warning"
                  :title="
                    core.$t('apps_lets_encrypt.lets_encrypt_disabled_warning')
                  "
                  :description="
                    core.$t(
                      'apps_lets_encrypt.lets_encrypt_disabled_warning_description',
                      {
                        node: this.status.node_ui_name
                          ? this.status.node_ui_name
                          : this.status.node,
                      }
                    )
                  "
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <NsToggle
              v-if="isConfigured"
              key="changeAdminPassword"
              value="changeAdminPassword"
              :label="$t('settings.change_admin_password')"
              v-model="isChangePassword"
              :disabled="stillLoading"
              class="mg-bottom"
            >
              <template slot="text-left">{{
                $t("settings.disabled")
              }}</template>
              <template slot="text-right">{{
                $t("settings.enabled")
              }}</template>
            </NsToggle>
            <NsPasswordInput
              v-if="isPasswordActive"
              key="adminPassword"
              :newPasswordLabel="$t('settings.admin_password')"
              :confirmPasswordLabel="$t('settings.admin_password_confirm')"
              v-model="adminPassword"
              @passwordValidation="onAdminPasswordValidation"
              :newPasswordInvalidMessage="$t(error.admin_password)"
              :confirmPasswordInvalidMessage="$t(error.admin_password_confirm)"
              :passwordHideLabel="core.$t('password.hide_password')"
              :passwordShowLabel="core.$t('password.show_password')"
              :lengthLabel="core.$t('password.long_enough')"
              :lowercaseLabel="core.$t('password.lowercase_letter')"
              :uppercaseLabel="core.$t('password.uppercase_letter')"
              :numberLabel="core.$t('password.number')"
              :symbolLabel="core.$t('password.symbol')"
              :equalLabel="core.$t('password.equal')"
              :focus="focusPasswordField"
              :minLength="12"
              :disabled="stillLoading"
              class="mg-bottom maxwidth"
            />
            <NsComboBox
              v-model="ldapDomain"
              :options="domains"
              auto-highlight
              :title="$t('settings.ldap_domain')"
              :label="$t('settings.choose_ldap_domain')"
              :invalid-message="$t(error.ldap_domain)"
              :disabled="stillLoading || loading.listUserDomains"
              tooltipAlignment="start"
              tooltipDirection="top"
              class="mg-bottom maxwidth"
              ref="ldap_domain"
            >
              <template slot="tooltip">{{
                $t("settings.ldap_domain_tooltip")
              }}</template>
            </NsComboBox>
            <cv-text-input
              v-if="ldapDomain && ldapDomain !== '-'"
              :label="$t('settings.ldap_admin_group')"
              placeholder="wazuh-admins"
              v-model.trim="ldapAdminGroup"
              class="mg-bottom maxwidth"
              :invalid-message="$t(error.ldap_admin_group)"
              :disabled="stillLoading"
              ref="ldap_admin_group"
            >
            </cv-text-input>
            <cv-text-input
              v-if="ldapDomain && ldapDomain !== '-'"
              :label="$t('settings.ldap_readonly_group')"
              :helper-text="$t('settings.ldap_readonly_group_helper')"
              placeholder="wazuh-readers"
              v-model.trim="ldapReadonlyGroup"
              class="mg-bottom maxwidth"
              :invalid-message="$t(error.ldap_readonly_group)"
              :disabled="stillLoading"
              ref="ldap_readonly_group"
            >
            </cv-text-input>
            <!-- advanced options -->
            <cv-accordion ref="accordion" class="maxwidth mg-bottom">
              <cv-accordion-item :open="isAdvancedOpen">
                <template slot="title">{{ $t("settings.advanced") }}</template>
                <template slot="content">
                  <NsToggle
                    value="indexUnclassified"
                    :label="$t('settings.index_unclassified_events')"
                    v-model="indexUnclassifiedEvents"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  >
                    <template #tooltip>{{
                      $t("settings.index_unclassified_events_tooltip")
                    }}</template>
                    <template slot="text-left">{{
                      $t("settings.disabled")
                    }}</template>
                    <template slot="text-right">{{
                      $t("settings.enabled")
                    }}</template>
                  </NsToggle>
                  <NsTextInput
                    type="number"
                    min="30"
                    max="3650"
                    v-model.number="retentionDays"
                    :label="$t('settings.retention_days')"
                    :helper-text="$t('settings.retention_days_helper')"
                    :invalid-message="$t(error.retention_days)"
                    :disabled="stillLoading"
                    class="mg-bottom"
                    ref="retention_days"
                  />
                  <cv-text-input
                    :label="$t('settings.export_url')"
                    placeholder="https://logs.example.org/wazuh"
                    v-model.trim="exportUrl"
                    class="mg-bottom"
                    :helper-text="$t('settings.export_url_helper')"
                    :invalid-message="$t(error.export_url)"
                    :disabled="stillLoading"
                    ref="export_url"
                  >
                  </cv-text-input>
                  <NsTextInput
                    v-if="exportUrl"
                    type="password"
                    v-model.trim="exportToken"
                    :label="$t('settings.export_token')"
                    :placeholder="
                      exportTokenSet ? $t('settings.export_token_set') : ''
                    "
                    :helper-text="$t('settings.export_token_helper')"
                    :passwordShowLabel="$t('settings.show')"
                    :passwordHideLabel="$t('settings.hide')"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  />
                  <h6 class="mg-bottom">
                    {{ $t("settings.notify_title") }}
                  </h6>
                  <NsInlineNotification
                    v-if="!smarthostEnabled"
                    kind="warning"
                    :title="$t('settings.smarthost_missing_title')"
                    :description="$t('settings.smarthost_missing_description')"
                    :actionLabel="$t('settings.go_to_smarthost')"
                    @action="goToSmarthost"
                    :showCloseButton="false"
                  />
                  <NsToggle
                    value="notifyEnabled"
                    :label="$t('settings.notify_enabled')"
                    v-model="notifyEnabled"
                    :disabled="stillLoading || !smarthostEnabled"
                    class="mg-bottom"
                  >
                    <template slot="text-left">{{
                      $t("settings.disabled")
                    }}</template>
                    <template slot="text-right">{{
                      $t("settings.enabled")
                    }}</template>
                  </NsToggle>
                  <template v-if="notifyEnabled">
                    <cv-text-area
                      v-model.trim="notifyRecipients"
                      :label="$t('settings.notify_recipients')"
                      :helper-text="$t('settings.notify_recipients_helper')"
                      :invalid-message="$t(error.notify_recipients)"
                      :disabled="stillLoading || !smarthostEnabled"
                      placeholder="soc@example.org"
                      class="mg-bottom"
                      ref="notify_recipients"
                    >
                    </cv-text-area>
                    <NsTextInput
                      v-model.trim="notifySender"
                      :label="$t('settings.notify_sender')"
                      :placeholder="
                        host ? 'wazuh@' + host : 'wazuh@example.org'
                      "
                      :helper-text="$t('settings.notify_sender_helper')"
                      :invalid-message="$t(error.notify_sender)"
                      :disabled="stillLoading || !smarthostEnabled"
                      class="mg-bottom"
                      ref="notify_sender"
                    />
                  </template>
                  <h6 class="mg-bottom">
                    {{ $t("settings.telegram_title") }}
                  </h6>
                  <NsToggle
                    value="telegramEnabled"
                    :label="$t('settings.telegram_enabled')"
                    v-model="telegramEnabled"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  >
                    <template slot="text-left">{{
                      $t("settings.disabled")
                    }}</template>
                    <template slot="text-right">{{
                      $t("settings.enabled")
                    }}</template>
                  </NsToggle>
                  <template v-if="telegramEnabled">
                    <div class="token-row">
                      <NsTextInput
                        type="password"
                        v-model.trim="telegramToken"
                        :label="$t('settings.telegram_token')"
                        :placeholder="
                          telegramTokenSet
                            ? $t('settings.telegram_token_set')
                            : ''
                        "
                        :invalid-message="$t(error.telegram_token)"
                        :passwordShowLabel="$t('settings.show')"
                        :passwordHideLabel="$t('settings.hide')"
                        :disabled="stillLoading"
                        class="token-field"
                        ref="telegram_token"
                      />
                      <NsButton
                        type="button"
                        v-if="telegramTokenSet"
                        kind="danger--tertiary"
                        size="field"
                        :disabled="stillLoading"
                        @click="isShownRemoveTokenModal = true"
                        class="side-button"
                        >{{ $t("settings.telegram_remove_token") }}</NsButton
                      >
                    </div>
                    <div class="field-helper mg-bottom">
                      {{ $t("settings.telegram_token_helper") }}
                    </div>
                    <NsToggle
                      value="telegramAdminEnabled"
                      :label="$t('settings.telegram_admin_enabled')"
                      v-model="telegramAdminEnabled"
                      :disabled="stillLoading || !telegramHasToken"
                      class="mg-bottom"
                    >
                      <template slot="text-left">{{
                        $t("settings.disabled")
                      }}</template>
                      <template slot="text-right">{{
                        $t("settings.enabled")
                      }}</template>
                    </NsToggle>
                    <TelegramChat
                      v-if="telegramAdminEnabled && !stillLoading"
                      :key="telegramChatKey"
                      v-model="telegramChatId"
                      :label="$t('settings.telegram_chat_id')"
                      :helper="$t('settings.telegram_chat_id_helper')"
                      :token="telegramToken"
                      :ready="telegramHasToken"
                      :invalidMessage="$t(error.telegram_chat_id)"
                      ref="telegram_chat_id"
                    />
                  </template>
                  <h6 class="mg-bottom">
                    {{ $t("settings.mattermost_title") }}
                  </h6>
                  <NsToggle
                    value="mattermostEnabled"
                    :label="$t('settings.mattermost_enabled')"
                    v-model="mattermostEnabled"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  >
                    <template slot="text-left">{{
                      $t("settings.disabled")
                    }}</template>
                    <template slot="text-right">{{
                      $t("settings.enabled")
                    }}</template>
                  </NsToggle>
                  <template v-if="mattermostEnabled">
                    <NsTextInput
                      type="password"
                      v-model.trim="mattermostWebhook"
                      :label="$t('settings.mattermost_webhook')"
                      :placeholder="
                        mattermostWebhookSet
                          ? $t('settings.mattermost_webhook_set')
                          : 'https://chat.example.com/hooks/…'
                      "
                      :helper-text="$t('settings.mattermost_webhook_helper')"
                      :invalid-message="$t(error.mattermost_webhook)"
                      :passwordShowLabel="$t('settings.show')"
                      :passwordHideLabel="$t('settings.hide')"
                      :disabled="stillLoading"
                      class="mg-bottom"
                      ref="mattermost_webhook"
                    />
                    <NsButton
                      type="button"
                      v-if="mattermostWebhookSet"
                      kind="danger--tertiary"
                      size="field"
                      :disabled="stillLoading"
                      @click="isShownRemoveMattermostSecretModal = true"
                      class="mg-bottom"
                      >{{ $t("settings.mattermost_webhook_remove") }}</NsButton
                    >
                    <NsTextInput
                      v-model.trim="mattermostChannel"
                      :label="$t('settings.mattermost_channel')"
                      :helper-text="$t('settings.mattermost_channel_helper')"
                      :invalid-message="$t(error.mattermost_channel)"
                      :disabled="stillLoading"
                      class="mg-bottom"
                      ref="mattermost_channel"
                    />
                    <NsTextInput
                      v-model.trim="mattermostUsername"
                      :label="$t('settings.mattermost_username')"
                      placeholder="Wazuh"
                      :helper-text="$t('settings.mattermost_username_helper')"
                      :invalid-message="$t(error.mattermost_username)"
                      :disabled="stillLoading"
                      class="mg-bottom"
                      ref="mattermost_username"
                    />
                    <NsButton
                      type="button"
                      kind="secondary"
                      size="field"
                      :loading="loading.testMattermost"
                      :disabled="stillLoading || loading.testMattermost"
                      @click="sendMattermostTest"
                      class="mg-bottom"
                      >{{ $t("settings.mattermost_test") }}</NsButton
                    >
                    <NsInlineNotification
                      v-if="mattermostTestSent"
                      kind="success"
                      :title="$t('settings.mattermost_test_sent')"
                      :showCloseButton="false"
                    />
                    <NsInlineNotification
                      v-if="error.testMattermost"
                      kind="error"
                      :title="$t('action.test-mattermost')"
                      :description="error.testMattermost"
                      :showCloseButton="false"
                    />
                  </template>
                  <!-- One level for every channel: the same findings reach the mailbox and the chat -->
                  <cv-dropdown
                    v-if="notifyEnabled || telegramEnabled || mattermostEnabled"
                    v-model="notifyMinLevel"
                    :label="$t('settings.notify_min_level')"
                    :helper-text="$t('settings.notify_min_level_helper')"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  >
                    <cv-dropdown-item
                      v-for="level in notifyLevels"
                      :key="level"
                      :value="level"
                      >{{ $t("settings.level_" + level) }}</cv-dropdown-item
                    >
                  </cv-dropdown>
                </template>
              </cv-accordion-item>
            </cv-accordion>
            <cv-row v-if="error.configureModule">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="$t('action.configure-module')"
                  :description="error.configureModule"
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <cv-row v-if="error.getStatus">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="$t('action.get-status')"
                  :description="error.getStatus"
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <cv-row v-if="validationErrorDetails.length">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="
                    core.$t('apps_lets_encrypt.cannot_obtain_certificate')
                  "
                  :showCloseButton="false"
                >
                  <template #description>
                    <div class="flex flex-col gap-2">
                      <div
                        v-for="(detail, index) in validationErrorDetails"
                        :key="index"
                      >
                        {{ detail }}
                      </div>
                    </div>
                  </template>
                </NsInlineNotification>
              </cv-column>
            </cv-row>
            <NsInlineNotification
              v-if="missingFields.length && !stillLoading"
              kind="info"
              :title="$t('settings.to_save')"
              :description="missingFields.join(', ')"
              :showCloseButton="false"
              class="mg-bottom maxwidth"
            />
            <NsButton
              kind="primary"
              :icon="Save20"
              :loading="loading.configureModule"
              :disabled="stillLoading || !isFormValid"
              >{{ $t("settings.save") }}</NsButton
            >
          </cv-form>
        </cv-tile>
      </cv-column>
    </cv-row>
    <NsModal
      size="default"
      kind="danger"
      :visible="isShownRemoveTokenModal"
      :primary-button-disabled="loading.configureModule"
      @modal-hidden="isShownRemoveTokenModal = false"
      @primary-click="removeTelegramToken"
    >
      <template slot="title">{{
        $t("settings.telegram_remove_token_title")
      }}</template>
      <template slot="content">
        <p>
          {{ $t("settings.telegram_remove_token_description") }}
        </p>
      </template>
      <template slot="secondary-button">{{
        core.$t("common.cancel")
      }}</template>
      <template slot="primary-button">{{
        $t("settings.telegram_remove_token")
      }}</template>
    </NsModal>
    <NsModal
      size="default"
      kind="danger"
      :visible="isShownRemoveMattermostSecretModal"
      :primary-button-disabled="loading.configureModule"
      @modal-hidden="isShownRemoveMattermostSecretModal = false"
      @primary-click="removeMattermostSecretConfirmed"
    >
      <template slot="title">{{
        $t("settings.mattermost_webhook_remove_title")
      }}</template>
      <template slot="content">
        <p>
          {{ $t("settings.mattermost_webhook_remove_description") }}
        </p>
      </template>
      <template slot="secondary-button">{{
        core.$t("common.cancel")
      }}</template>
      <template slot="primary-button">{{
        $t("settings.mattermost_webhook_remove")
      }}</template>
    </NsModal>
  </cv-grid>
</template>

<script>
import to from "await-to-js";
import { mapState } from "vuex";
import { CHAT_ID_PATTERN, TOKEN_PATTERN } from "../lib/telegram";
import TelegramChat from "@/components/TelegramChat.vue";
import {
  WEBHOOK_PATTERN as MATTERMOST_WEBHOOK_PATTERN,
  CHANNEL_PATTERN as MATTERMOST_CHANNEL_PATTERN,
  USERNAME_PATTERN as MATTERMOST_USERNAME_PATTERN,
  testMattermost,
} from "../lib/mattermost";
import {
  QueryParamService,
  UtilService,
  TaskService,
  IconService,
  PageTitleService,
} from "@nethserver/ns8-ui-lib";

export default {
  name: "Settings",
  mixins: [
    TaskService,
    IconService,
    UtilService,
    QueryParamService,
    PageTitleService,
  ],
  components: { TelegramChat },
  pageTitle() {
    return this.$t("settings.title") + " - " + this.appName;
  },
  data() {
    return {
      q: {
        page: "settings",
      },
      status: {},
      validationErrorDetails: [],
      urlCheckInterval: null,
      host: "",
      configuredHost: "",
      agentsEnrolled: 0,
      adminPassword: "",
      adminPasswordValidation: null,
      focusPasswordField: { element: "" },
      isChangePassword: false,
      isAdvancedOpen: false,
      isLetsEncryptEnabled: false,
      isLetsEncryptCurrentlyEnabled: false,
      // Empty until the list of domains and the configuration are both loaded: NsComboBox
      // writes its label only when the value changes while the option already exists
      ldapDomain: "",
      configuredLdapDomain: null,
      ldapAdminGroup: "",
      ldapReadonlyGroup: "",
      domains: [],
      indexUnclassifiedEvents: false,
      retentionDays: 365,
      exportUrl: "",
      notifyEnabled: false,
      notifyRecipients: "",
      notifySender: "",
      notifyMinLevel: "medium",
      notifyLevels: ["low", "medium", "high", "critical"],
      smarthostEnabled: true,
      exportToken: "",
      exportTokenSet: false,
      telegramEnabled: false,
      telegramToken: "",
      telegramTokenSet: false,
      telegramAdminEnabled: false,
      telegramChatId: "",
      // Changed on each load: the chat field starts over with the saved chat
      telegramChatKey: 0,
      telegramRemoveToken: false,
      mattermostEnabled: false,
      mattermostWebhook: "",
      mattermostWebhookSet: false,
      mattermostChannel: "",
      mattermostUsername: "",
      mattermostTestSent: false,
      isShownRemoveTokenModal: false,
      isShownRemoveMattermostSecretModal: false,
      removeMattermostSecret: false,
      loading: {
        getConfiguration: false,
        configureModule: false,
        getStatus: false,
        listUserDomains: false,
        testMattermost: false,
      },
      error: {
        admin_password: "",
        admin_password_confirm: "",
        ldap_domain: "",
        ldap_admin_group: "",
        ldap_readonly_group: "",
        retention_days: "",
        export_url: "",
        notify_recipients: "",
        notify_sender: "",
        telegram_token: "",
        telegram_chat_id: "",
        mattermost_webhook: "",
        mattermost_channel: "",
        mattermost_username: "",
        testMattermost: "",
        listUserDomains: "",
        getConfiguration: "",
        configureModule: "",
        host: "",
        lets_encrypt: "",
        getStatus: "",
      },
    };
  },
  watch: {
    // No admin chat without a bot to write to it
    telegramHasToken(hasToken) {
      if (!hasToken) {
        this.telegramAdminEnabled = false;
      }
    },
    adminPassword() {
      this.error.admin_password = "";
      this.error.admin_password_confirm = "";
    },
    isChangePassword() {
      this.adminPassword = "";
      this.error.admin_password = "";
      this.error.admin_password_confirm = "";
    },
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
    telegramHasToken() {
      return this.telegramTokenSet || !!this.telegramToken;
    },
    stillLoading() {
      return (
        this.loading.getConfiguration ||
        this.loading.configureModule ||
        this.loading.getStatus
      );
    },
    // The first configuration must choose the password, a later one may keep it
    isConfigured() {
      return this.configuredHost !== "";
    },
    isPasswordActive() {
      // Wait for the configuration: before it loads, every module looks unconfigured
      if (this.loading.getConfiguration) {
        return false;
      }
      return !this.isConfigured || this.isChangePassword;
    },
    isHostLocked() {
      // null means the API did not answer: lock too, the backend refuses the change anyway
      return this.isConfigured && this.agentsEnrolled !== 0;
    },
    hostHelperText() {
      if (!this.isConfigured) {
        return "";
      }
      if (this.isHostLocked) {
        return this.$t("settings.host_locked_helper");
      }
      return this.$t("settings.host_bound_helper");
    },
    passwordError() {
      // Same rules as the backend: Wazuh refuses other characters than these ones
      const value = this.adminPassword;
      if (value.length < 12 || value.length > 64) {
        return "settings.password_length";
      }
      if (!/^[A-Za-z0-9.,_+:@%^=~-]+$/.test(value)) {
        return "settings.password_characters";
      }
      if (
        !/[A-Z]/.test(value) ||
        !/[a-z]/.test(value) ||
        !/[0-9]/.test(value) ||
        !/[.,_+:@%^=~-]/.test(value)
      ) {
        return "settings.password_classes";
      }
      return "";
    },
    isDomainChosen() {
      return this.ldapDomain !== "" && this.ldapDomain !== "-";
    },
    missingFields() {
      const missing = [];
      if (!this.host || !this.host.includes(".")) {
        missing.push(this.$t("settings.wazuh_fqdn"));
      }
      if (!this.adminPassword && this.isPasswordActive) {
        missing.push(this.$t("settings.admin_password"));
      }
      if (this.isDomainChosen && !this.ldapAdminGroup) {
        missing.push(this.$t("settings.ldap_admin_group"));
      }
      if (
        this.notifyEnabled &&
        (!this.recipientList.length ||
          this.recipientList.some((r) => !this.isEmail(r)))
      ) {
        missing.push(this.$t("settings.notify_recipients"));
      }
      if (this.exportUrl && !this.exportUrl.startsWith("https://")) {
        missing.push(this.$t("settings.export_url"));
      }
      return missing;
    },
    recipientList() {
      return this.notifyRecipients.split(/[\s,;]+/).filter((r) => r !== "");
    },
    isFormValid() {
      return this.missingFields.length === 0;
    },
  },
  created() {
    this.listUserDomains();
    this.getConfiguration();
    this.getStatus();
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      vm.watchQueryData(vm);
      vm.urlCheckInterval = vm.initUrlBindingForApp(vm, vm.q.page);
    });
  },
  beforeRouteLeave(to, from, next) {
    clearInterval(this.urlCheckInterval);
    next();
  },
  methods: {
    onAdminPasswordValidation(validation) {
      this.adminPasswordValidation = validation;
    },
    isEmail(value) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    },
    goToSmarthost() {
      this.core.$router.push("/settings/smarthost");
    },
    async listUserDomains() {
      this.loading.listUserDomains = true;
      this.error.listUserDomains = "";
      const taskAction = "list-user-domains";
      this.core.$root.$off(taskAction + "-aborted");
      this.core.$root.$once(
        taskAction + "-aborted",
        this.listUserDomainsAborted
      );
      this.core.$root.$off(taskAction + "-completed");
      this.core.$root.$once(
        taskAction + "-completed",
        this.listUserDomainsCompleted
      );
      const res = await to(
        this.createClusterTaskForApp({
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.listUserDomains = this.getErrorMessage(err);
        this.loading.listUserDomains = false;
      }
    },
    listUserDomainsAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.listUserDomains = this.$t("error.generic_error");
      this.loading.listUserDomains = false;
    },
    listUserDomainsCompleted(taskContext, taskResult) {
      const options = taskResult.output.domains.map((domain) => ({
        name: domain.name,
        label: domain.name,
        value: domain.name,
      }));
      options.unshift({
        name: "no_user_domain",
        label: this.$t("settings.no_user_domain"),
        value: "-",
      });
      this.domains = options;
      this.loading.listUserDomains = false;
      this.applyLdapDomain();
    },
    applyLdapDomain() {
      if (this.configuredLdapDomain !== null && this.domains.length) {
        this.ldapDomain = this.configuredLdapDomain;
      }
    },
    goToCertificates() {
      this.core.$router.push("/settings/tls-certificates");
    },
    async getStatus() {
      this.loading.getStatus = true;
      this.error.getStatus = "";
      const taskAction = "get-status";
      const eventId = this.getUuid();
      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.getStatusAborted
      );
      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.getStatusCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.getStatus = this.getErrorMessage(err);
        this.loading.getStatus = false;
        return;
      }
    },
    getStatusAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.getStatus = this.$t("error.generic_error");
      this.loading.getStatus = false;
    },
    getStatusCompleted(taskContext, taskResult) {
      this.status = taskResult.output;
      this.loading.getStatus = false;
    },
    async getConfiguration() {
      this.loading.getConfiguration = true;
      this.error.getConfiguration = "";
      const taskAction = "get-configuration";
      const eventId = this.getUuid();

      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.getConfigurationAborted
      );

      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.getConfigurationCompleted
      );

      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.getConfiguration = this.getErrorMessage(err);
        this.loading.getConfiguration = false;
        return;
      }
    },
    getConfigurationAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.getConfiguration = this.$t("error.generic_error");
      this.loading.getConfiguration = false;
    },
    getConfigurationCompleted(taskContext, taskResult) {
      const config = taskResult.output;
      this.host = config.host;
      this.configuredHost = config.host;
      this.agentsEnrolled = config.agents_enrolled;
      this.isLetsEncryptEnabled = config.lets_encrypt;
      this.isLetsEncryptCurrentlyEnabled = config.lets_encrypt;
      this.configuredLdapDomain =
        config.ldap_domain === "" ? "-" : config.ldap_domain;
      this.applyLdapDomain();
      this.ldapAdminGroup = config.ldap_admin_group;
      this.ldapReadonlyGroup = config.ldap_readonly_group || "";
      this.indexUnclassifiedEvents = config.index_unclassified_events;
      this.retentionDays = config.retention_days;
      this.exportUrl = config.export_url;
      this.notifyEnabled = config.notify_enabled;
      this.notifyRecipients = config.notify_recipients.join("\n");
      this.notifySender = config.notify_sender;
      this.notifyMinLevel = config.notify_min_level;
      this.smarthostEnabled = config.smarthost_enabled;
      this.exportTokenSet = config.export_token_set;
      this.exportToken = "";
      this.telegramEnabled = config.telegram_enabled;
      this.telegramAdminEnabled =
        config.telegram_admin_enabled && config.telegram_token_set;
      this.telegramChatId = config.telegram_chat_id;
      this.telegramTokenSet = config.telegram_token_set;
      this.telegramToken = "";
      this.telegramRemoveToken = false;
      this.telegramChatKey++;
      this.mattermostEnabled = config.mattermost_enabled;
      this.mattermostWebhookSet = config.mattermost_webhook_set;
      this.mattermostWebhook = "";
      this.removeMattermostSecret = false;
      this.mattermostChannel = config.mattermost_channel;
      this.mattermostUsername = config.mattermost_username;

      // Show the advanced options when one of them is in use
      this.isAdvancedOpen =
        config.index_unclassified_events ||
        config.retention_days !== 365 ||
        config.export_url !== "" ||
        config.notify_enabled ||
        config.telegram_enabled ||
        config.mattermost_enabled;
      this.loading.getConfiguration = false;
      this.focusElement("host");
    },
    validateConfigureModule() {
      this.clearErrors(this);
      this.validationErrorDetails = [];
      let isValidationOk = true;
      if (!this.host) {
        this.error.host = "common.required";

        if (isValidationOk) {
          this.focusElement("host");
        }
        isValidationOk = false;
      }
      if (this.isPasswordActive) {
        const v = this.adminPasswordValidation;
        // The meter does not check the maximum length nor the allowed symbols
        const passwordError =
          v &&
          v.isLengthOk &&
          v.isLowercaseOk &&
          v.isUppercaseOk &&
          v.isNumberOk &&
          v.isSymbolOk
            ? this.passwordError
            : "settings.admin_password_too_weak";
        if (passwordError) {
          this.error.admin_password = passwordError;
          if (isValidationOk) {
            this.focusPasswordField = { element: "newPassword" };
          }
          isValidationOk = false;
        } else if (!v.isEqualOk) {
          this.error.admin_password_confirm =
            "settings.admin_password_mismatch";
          if (isValidationOk) {
            this.focusPasswordField = { element: "confirmPassword" };
          }
          isValidationOk = false;
        }
      }
      if (this.ldapDomain && this.ldapDomain !== "-" && !this.ldapAdminGroup) {
        this.error.ldap_admin_group = "common.required";
        if (isValidationOk) {
          this.focusElement("ldap_admin_group");
        }
        isValidationOk = false;
      }
      if (
        this.notifyEnabled &&
        this.recipientList.some((r) => !this.isEmail(r))
      ) {
        this.error.notify_recipients = "settings.notify_recipients_invalid";
        if (isValidationOk) {
          this.focusElement("notify_recipients");
        }
        isValidationOk = false;
      }
      if (
        this.notifyEnabled &&
        this.notifySender &&
        !this.isEmail(this.notifySender)
      ) {
        this.error.notify_sender = "settings.notify_sender_invalid";
        if (isValidationOk) {
          this.focusElement("notify_sender");
        }
        isValidationOk = false;
      }
      if (this.telegramToken && !TOKEN_PATTERN.test(this.telegramToken)) {
        this.error.telegram_token = "settings.telegram_token_pattern";
        if (isValidationOk) {
          this.focusElement("telegram_token");
        }
        isValidationOk = false;
      }
      if (
        this.telegramEnabled &&
        !this.telegramToken &&
        !this.telegramTokenSet
      ) {
        this.error.telegram_token = "common.required";
        if (isValidationOk) {
          this.focusElement("telegram_token");
        }
        isValidationOk = false;
      }
      if (
        this.telegramEnabled &&
        this.telegramAdminEnabled &&
        !CHAT_ID_PATTERN.test(this.telegramChatId)
      ) {
        this.error.telegram_chat_id = this.telegramChatId
          ? "settings.telegram_chat_id_invalid"
          : "common.required";
        if (isValidationOk) {
          this.$refs.telegram_chat_id.focus();
        }
        isValidationOk = false;
      }
      if (this.mattermostEnabled) {
        if (
          this.mattermostWebhook
            ? !MATTERMOST_WEBHOOK_PATTERN.test(this.mattermostWebhook)
            : !this.mattermostWebhookSet
        ) {
          this.error.mattermost_webhook = this.mattermostWebhook
            ? "settings.mattermost_webhook_invalid"
            : "common.required";
          if (isValidationOk) {
            this.focusElement("mattermost_webhook");
          }
          isValidationOk = false;
        }
        if (
          this.mattermostChannel &&
          !MATTERMOST_CHANNEL_PATTERN.test(this.mattermostChannel)
        ) {
          this.error.mattermost_channel = "settings.mattermost_channel_invalid";
          if (isValidationOk) {
            this.focusElement("mattermost_channel");
          }
          isValidationOk = false;
        }
        if (!MATTERMOST_USERNAME_PATTERN.test(this.mattermostUsername)) {
          this.error.mattermost_username =
            "settings.mattermost_username_invalid";
          if (isValidationOk) {
            this.focusElement("mattermost_username");
          }
          isValidationOk = false;
        }
      }
      if (
        !Number.isInteger(this.retentionDays) ||
        this.retentionDays < 30 ||
        this.retentionDays > 3650
      ) {
        this.error.retention_days = "settings.retention_days_range";
        if (isValidationOk) {
          this.isAdvancedOpen = true;
          this.focusElement("retention_days");
        }
        isValidationOk = false;
      }
      if (this.exportUrl && !this.exportUrl.startsWith("https://")) {
        this.error.export_url = "settings.export_url_https";
        if (isValidationOk) {
          this.focusElement("export_url");
        }
        isValidationOk = false;
      }
      return isValidationOk;
    },
    configureModuleValidationFailed(validationErrors) {
      this.loading.configureModule = false;
      let focusAlreadySet = false;
      for (const validationError of validationErrors) {
        const param = validationError.parameter;
        if (validationError.details) {
          // show inline error notification with details
          this.validationErrorDetails = validationError.details
            .split("\n")
            .filter((detail) => detail.trim() !== "");
        } else {
          // set i18n error message
          this.error[param] = this.$t("settings." + validationError.error);
          if (!focusAlreadySet) {
            if (param === "admin_password") {
              this.focusPasswordField = { element: "newPassword" };
            } else {
              this.focusElement(param);
            }
            focusAlreadySet = true;
          }
        }
      }
    },
    async sendMattermostTest() {
      this.mattermostTestSent = false;
      this.error.testMattermost = "";
      this.error.mattermost_webhook = "";
      this.error.mattermost_channel = "";
      if (
        this.mattermostWebhook
          ? !MATTERMOST_WEBHOOK_PATTERN.test(this.mattermostWebhook)
          : !this.mattermostWebhookSet
      ) {
        this.error.mattermost_webhook = this.mattermostWebhook
          ? "settings.mattermost_webhook_invalid"
          : "common.required";
        return;
      }
      if (
        this.mattermostChannel &&
        !MATTERMOST_CHANNEL_PATTERN.test(this.mattermostChannel)
      ) {
        this.error.mattermost_channel = "settings.mattermost_channel_invalid";
        return;
      }
      this.loading.testMattermost = true;
      const data = {
        channel: this.mattermostChannel,
        username: MATTERMOST_USERNAME_PATTERN.test(this.mattermostUsername)
          ? this.mattermostUsername
          : "",
      };
      // A typed webhook is tested before it is saved, else the backend takes the stored one
      if (this.mattermostWebhook) {
        data.webhook = this.mattermostWebhook;
      }
      const result = await testMattermost(this, data);
      this.loading.testMattermost = false;
      if ("output" in result) {
        this.mattermostTestSent = true;
      } else if (result.parameter === "channel") {
        this.error.mattermost_channel = result.message;
      } else {
        this.error.testMattermost = result.message;
      }
    },
    removeMattermostSecretConfirmed() {
      this.isShownRemoveMattermostSecretModal = false;
      // Without it nothing could be sent: the switch goes off with it
      this.removeMattermostSecret = true;
      this.mattermostEnabled = false;
      this.mattermostWebhook = "";
      this.configureModule();
    },
    removeTelegramToken() {
      this.isShownRemoveTokenModal = false;
      // Without a token nothing could be sent: the bot switch goes off with it
      this.telegramRemoveToken = true;
      this.telegramEnabled = false;
      this.telegramToken = "";
      // The admin chat goes with the bot: the next token starts from an empty field
      this.telegramAdminEnabled = false;
      this.telegramChatId = "";
      this.configureModule();
    },
    async configureModule() {
      this.error.test_imap = false;
      this.error.test_smtp = false;
      const isValidationOk = this.validateConfigureModule();
      if (!isValidationOk) {
        return;
      }

      this.loading.configureModule = true;
      const taskAction = "configure-module";
      const eventId = this.getUuid();

      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.configureModuleAborted
      );

      // register to task validation
      this.core.$root.$once(
        `${taskAction}-validation-failed-${eventId}`,
        this.configureModuleValidationFailed
      );

      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.configureModuleCompleted
      );
      const data = {
        host: this.host,
        lets_encrypt: this.isLetsEncryptEnabled,
        ldap_domain: this.ldapDomain === "-" ? "" : this.ldapDomain,
        ldap_admin_group: this.ldapDomain === "-" ? "" : this.ldapAdminGroup,
        ldap_readonly_group:
          this.ldapDomain === "-" ? "" : this.ldapReadonlyGroup,
        index_unclassified_events: this.indexUnclassifiedEvents,
        retention_days: this.retentionDays,
        export_url: this.exportUrl,
        notify_enabled: this.notifyEnabled,
        // While the emails are off the fields are hidden: keep only what the backend accepts
        notify_recipients: [
          ...new Set(this.recipientList.filter((r) => this.isEmail(r))),
        ],
        notify_sender: this.isEmail(this.notifySender) ? this.notifySender : "",
        notify_min_level: this.notifyMinLevel,
        telegram_enabled: this.telegramEnabled,
        telegram_admin_enabled: this.telegramAdminEnabled,
        // While Telegram is off the field is hidden: keep only what the backend accepts
        telegram_chat_id: CHAT_ID_PATTERN.test(this.telegramChatId)
          ? this.telegramChatId
          : "",
        mattermost_enabled: this.mattermostEnabled,
        // While Mattermost is off the fields are hidden: keep only what the backend accepts
        mattermost_channel: MATTERMOST_CHANNEL_PATTERN.test(
          this.mattermostChannel
        )
          ? this.mattermostChannel
          : "",
        mattermost_username: MATTERMOST_USERNAME_PATTERN.test(
          this.mattermostUsername
        )
          ? this.mattermostUsername
          : "",
      };
      // Without a new password the backend keeps the current one
      if (this.isPasswordActive) {
        data.admin_password = this.adminPassword;
      }
      // Only send the token when typed, an empty one would remove the stored token
      if (this.exportToken) {
        data.export_token = this.exportToken;
      } else if (!this.exportUrl) {
        data.export_token = "";
      }
      // Same for the other secrets: turning a channel off keeps them for later
      if (
        this.mattermostWebhook &&
        MATTERMOST_WEBHOOK_PATTERN.test(this.mattermostWebhook)
      ) {
        data.mattermost_webhook = this.mattermostWebhook;
      } else if (this.removeMattermostSecret) {
        data.mattermost_webhook = "";
      }
      if (this.telegramToken) {
        data.telegram_token = this.telegramToken;
      } else if (this.telegramRemoveToken) {
        data.telegram_token = "";
      }
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data,
          extra: {
            title: this.$t("settings.instance_configuration", {
              instance: this.instanceName,
            }),
            description: this.$t("settings.configuring"),
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.configureModule = this.getErrorMessage(err);
        this.loading.configureModule = false;
        return;
      }
    },
    configureModuleAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.configureModule = this.$t("error.generic_error");
      this.loading.configureModule = false;
    },
    configureModuleCompleted() {
      this.loading.configureModule = false;
      // Do not keep the password in the page once it is applied
      this.adminPassword = "";
      this.isChangePassword = false;

      // reload configuration
      this.getConfiguration();
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
.mg-bottom {
  margin-bottom: $spacing-06;
}

.token-row {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: $spacing-05;
}

.token-field {
  flex: 0 1 20rem;
}

// Level with the field, not with its label or its error below
.side-button {
  margin-top: $spacing-06;
}

.field-helper {
  margin-top: $spacing-03;
  font-size: 0.75rem;
  color: $text-02;
}

.maxwidth {
  max-width: 38rem;
}
</style>
