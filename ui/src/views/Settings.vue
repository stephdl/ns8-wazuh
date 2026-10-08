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
            <cv-text-input
              :label="$t('settings.wazuh_fqdn')"
              placeholder="wazuh.example.org"
              v-model.trim="host"
              class="mg-bottom"
              :invalid-message="$t(error.host)"
              :disabled="loading.getConfiguration || loading.configureModule"
              ref="host"
            >
            </cv-text-input>
            <NsTextInput
              type="password"
              v-model="adminPassword"
              autocomplete="new-password"
              :label="$t('settings.admin_password')"
              :placeholder="
                isConfigured
                  ? $t('settings.unchanged_password_placeholder')
                  : ''
              "
              :helper-text="$t('settings.admin_password_rules')"
              :invalid-message="$t(error.admin_password)"
              :passwordShowLabel="$t('settings.show')"
              :passwordHideLabel="$t('settings.hide')"
              :disabled="stillLoading"
              class="mg-bottom maxwidth"
              ref="admin_password"
            />
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
                    v-model="exportToken"
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
  </cv-grid>
</template>

<script>
import to from "await-to-js";
import { mapState } from "vuex";
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
      adminPassword: "",
      isAdvancedOpen: false,
      isLetsEncryptEnabled: false,
      isLetsEncryptCurrentlyEnabled: false,
      // Empty until the list of domains and the configuration are both loaded: NsComboBox
      // writes its label only when the value changes while the option already exists
      ldapDomain: "",
      configuredLdapDomain: null,
      ldapAdminGroup: "",
      domains: [],
      indexUnclassifiedEvents: false,
      exportUrl: "",
      exportToken: "",
      exportTokenSet: false,
      loading: {
        getConfiguration: false,
        configureModule: false,
        getStatus: false,
        listUserDomains: false,
      },
      error: {
        admin_password: "",
        ldap_domain: "",
        ldap_admin_group: "",
        export_url: "",
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
    adminPassword() {
      this.error.admin_password = "";
    },
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
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
      if (!this.adminPassword && !this.isConfigured) {
        missing.push(this.$t("settings.admin_password"));
      }
      if (this.isDomainChosen && !this.ldapAdminGroup) {
        missing.push(this.$t("settings.ldap_admin_group"));
      }
      if (this.exportUrl && !this.exportUrl.startsWith("https://")) {
        missing.push(this.$t("settings.export_url"));
      }
      return missing;
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
      this.isLetsEncryptEnabled = config.lets_encrypt;
      this.isLetsEncryptCurrentlyEnabled = config.lets_encrypt;
      this.configuredLdapDomain =
        config.ldap_domain === "" ? "-" : config.ldap_domain;
      this.applyLdapDomain();
      this.ldapAdminGroup = config.ldap_admin_group;
      this.indexUnclassifiedEvents = config.index_unclassified_events;
      this.exportUrl = config.export_url;
      this.exportTokenSet = config.export_token_set;
      this.exportToken = "";

      // Show the advanced options when one of them is in use
      this.isAdvancedOpen =
        config.index_unclassified_events || config.export_url !== "";
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
      if (this.adminPassword && this.passwordError) {
        this.error.admin_password = this.passwordError;
        if (isValidationOk) {
          this.focusElement("admin_password");
        }
        isValidationOk = false;
      }
      if (this.ldapDomain && this.ldapDomain !== "-" && !this.ldapAdminGroup) {
        this.error.ldap_admin_group = "common.required";
        if (isValidationOk) {
          this.focusElement("ldap_admin_group");
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
            this.focusElement(param);
            focusAlreadySet = true;
          }
        }
      }
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
        index_unclassified_events: this.indexUnclassifiedEvents,
        export_url: this.exportUrl,
      };
      // The password is sent only when typed: nothing means keep the current one
      if (this.adminPassword) {
        data.admin_password = this.adminPassword;
      }
      // Only send the token when typed, an empty one would remove the stored token
      if (this.exportToken) {
        data.export_token = this.exportToken;
      } else if (!this.exportUrl) {
        data.export_token = "";
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

.maxwidth {
  max-width: 38rem;
}
</style>
