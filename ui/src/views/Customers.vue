<!--
  Copyright (C) 2026 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <cv-grid fullWidth>
    <cv-row>
      <cv-column class="page-title">
        <h2>{{ $t("customers.title") }}</h2>
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <NsInlineNotification
          kind="info"
          :title="$t('customers.zones_title')"
          :description="$t('customers.zones_description')"
          :actionLabel="$t('customers.zones_doc')"
          @action="openUrl(zonesDocUrl)"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <cv-tile light>
          <div class="toolbar">
            <NsButton
              kind="secondary"
              :icon="Restart20"
              :loading="loading.listCustomers"
              :disabled="loading.listCustomers"
              @click="listCustomers"
              >{{ $t("customers.refresh") }}</NsButton
            >
          </div>
          <NsInlineNotification
            v-if="error.removeCustomer"
            kind="error"
            :title="$t('action.remove-customer')"
            :description="error.removeCustomer"
            :showCloseButton="false"
          />
          <NsDataTable
            :allRows="customers"
            :columns="i18nTableColumns"
            :rawColumns="tableColumns"
            :sortable="true"
            :pageSizes="[10, 25, 50, 100]"
            :overflow-menu="true"
            isSearchable
            :searchPlaceholder="$t('customers.search')"
            :searchClearLabel="core.$t('common.clear_search')"
            :noSearchResultsLabel="core.$t('common.no_search_results')"
            :noSearchResultsDescription="
              core.$t('common.no_search_results_description')
            "
            :isLoading="loading.listCustomers"
            :skeletonRows="3"
            :isErrorShown="!!error.listCustomers"
            :errorTitle="$t('action.list-customers')"
            :errorDescription="error.listCustomers"
            :itemsPerPageLabel="core.$t('pagination.items_per_page')"
            :rangeOfTotalItemsLabel="core.$t('pagination.range_of_total_items')"
            :ofTotalPagesLabel="core.$t('pagination.of_total_pages')"
            :backwardText="core.$t('pagination.previous_page')"
            :forwardText="core.$t('pagination.next_page')"
            :pageNumberLabel="core.$t('pagination.page_number')"
            @updatePage="tablePage = $event"
          >
            <template slot="empty-state">
              <NsEmptyState
                :title="$t('customers.no_customers')"
                :description="$t('customers.no_customers_description')"
              />
            </template>
            <template slot="data">
              <cv-data-table-row
                v-for="(row, rowIndex) in tablePage"
                :key="`${rowIndex}`"
                :value="`${rowIndex}`"
              >
                <cv-data-table-cell>{{ row.name }}</cv-data-table-cell>
                <cv-data-table-cell>{{ row.agents }}</cv-data-table-cell>
                <cv-data-table-cell>
                  <span v-if="!row.zones.length" class="muted">{{
                    $t("customers.not_watched")
                  }}</span>
                  <NsTag
                    v-for="zone in row.zones"
                    :key="zone"
                    :label="zoneText(zone)"
                    kind="blue"
                    size="sm"
                  />
                </cv-data-table-cell>
                <cv-data-table-cell>{{
                  row.recipients.join(", ") || "-"
                }}</cv-data-table-cell>
                <cv-data-table-cell>{{
                  (row.telegram_enabled && row.telegram_chat_id) || "-"
                }}</cv-data-table-cell>
                <cv-data-table-cell class="table-overflow-menu-cell">
                  <cv-overflow-menu flip-menu class="table-overflow-menu">
                    <cv-overflow-menu-item @click="showEditModal(row)">
                      <NsMenuItem :icon="Edit20" :label="$t('customers.edit')" />
                    </cv-overflow-menu-item>
                    <NsMenuDivider />
                    <cv-overflow-menu-item
                      danger
                      :disabled="row.agents > 0"
                      @click="showRemoveModal(row)"
                    >
                      <NsMenuItem
                        :icon="TrashCan20"
                        :label="$t('customers.remove')"
                      />
                    </cv-overflow-menu-item>
                  </cv-overflow-menu>
                </cv-data-table-cell>
              </cv-data-table-row>
            </template>
          </NsDataTable>
        </cv-tile>
      </cv-column>
    </cv-row>
    <NsModal
      size="default"
      :visible="!!customerToEdit"
      :primary-button-disabled="loading.setCustomer"
      :isLoading="loading.setCustomer"
      @modal-hidden="hideEditModal"
      @primary-click="setCustomer"
    >
      <template slot="title">{{
        $t("customers.edit_title", {
          name: customerToEdit ? customerToEdit.name : "",
        })
      }}</template>
      <template slot="content">
        <cv-form @submit.prevent="setCustomer">
          <NsMultiSelect
            v-model="zones"
            :options="zoneOptions"
            :title="$t('customers.zones')"
            :label="$t('customers.choose_zones')"
            :helper-text="$t('customers.zones_helper')"
            :invalid-message="$t(error.zones)"
            :filterable="true"
            :maxDisplayOptions="300"
            :auto-filter="true"
            :auto-highlight="true"
            :disabled="loading.setCustomer"
            showSelectedItems
            :unselectAriaLabel="core.$t('common.unselect')"
            :clearSelectionAriaLabel="core.$t('common.clear_selection')"
            :clearFilterLabel="core.$t('common.clear_filter')"
            :selectedLabel="core.$t('common.selected_l')"
            :userInputLabel="core.$t('common.user_input_l')"
            class="mg-bottom"
            ref="zones"
          />
          <cv-text-area
            v-model.trim="recipients"
            :label="$t('customers.recipients')"
            :helper-text="$t('customers.recipients_helper')"
            :invalid-message="$t(error.recipients)"
            :disabled="loading.setCustomer"
            placeholder="soc@example.org"
            class="mg-bottom"
            ref="recipients"
          />
          <template v-if="telegramReady">
            <NsToggle
              value="telegramEnabled"
              :label="$t('customers.telegram_enabled')"
              v-model="telegramEnabled"
              :disabled="loading.setCustomer"
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
              v-if="telegramEnabled"
              :key="customerToEdit ? customerToEdit.name : ''"
              v-model="telegramChatId"
              :label="$t('customers.telegram_chat_id')"
              :helper="$t('customers.telegram_chat_id_helper')"
              :disabled="loading.setCustomer"
              :invalidMessage="$t(error.telegram_chat_id)"
              ref="telegram_chat_id"
            />
          </template>
          <p v-else class="mg-bottom muted">
            {{ $t("customers.telegram_no_token") }}
          </p>
          <NsInlineNotification
            v-if="
              !zones.length &&
              (recipientList.length || (telegramEnabled && telegramChatId))
            "
            kind="warning"
            :title="$t('customers.no_zones_title')"
            :description="$t('customers.no_zones_description')"
            :showCloseButton="false"
          />
          <NsInlineNotification
            v-if="!smarthostEnabled && recipientList.length"
            kind="warning"
            :title="$t('settings.smarthost_missing_title')"
            :description="$t('settings.smarthost_missing_description')"
            :showCloseButton="false"
          />
          <NsInlineNotification
            v-if="error.setCustomer"
            kind="error"
            :title="$t('action.set-customer')"
            :description="error.setCustomer"
            :showCloseButton="false"
          />
        </cv-form>
      </template>
      <template slot="secondary-button">{{ core.$t("common.cancel") }}</template>
      <template slot="primary-button">{{ $t("customers.save") }}</template>
    </NsModal>
    <NsDangerDeleteModal
      :isShown="!!customerToRemove"
      :name="customerToRemove ? customerToRemove.name : ''"
      :title="$t('customers.remove_title')"
      :warning="$t('customers.remove_warning')"
      :description="$t('customers.remove_description')"
      :typeToConfirm="
        $t('customers.remove_type_to_confirm', {
          name: customerToRemove ? customerToRemove.name : '',
        })
      "
      :deleteLabel="$t('customers.remove')"
      :cancelLabel="core.$t('common.cancel')"
      :loading="loading.removeCustomer"
      @hide="customerToRemove = null"
      @confirmDelete="removeCustomer"
    />
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
import { zoneLabel, zoneOptions } from "../lib/countries";
import { CHAT_ID_PATTERN } from "../lib/telegram";
import TelegramChat from "@/components/TelegramChat.vue";

export default {
  name: "Customers",
  mixins: [
    TaskService,
    IconService,
    UtilService,
    QueryParamService,
    PageTitleService,
  ],
  components: { TelegramChat },
  pageTitle() {
    return this.$t("customers.title") + " - " + this.appName;
  },
  data() {
    return {
      q: {
        page: "customers",
      },
      urlCheckInterval: null,
      zonesDocUrl: "https://github.com/stephdl/ns8-wazuh/blob/main/README.md#login-zones",
      customers: [],
      countries: [],
      continents: {},
      tablePage: [],
      tableColumns: ["name", "agents", "zones", "recipients", "telegram"],
      customerToEdit: null,
      customerToRemove: null,
      zones: [],
      recipients: "",
      telegramEnabled: false,
      telegramChatId: "",
      smarthostEnabled: true,
      // The bot of the module is on and has a token: a customer chat can get alerts
      telegramReady: false,
      loading: {
        listCustomers: false,
        setCustomer: false,
        removeCustomer: false,
      },
      error: {
        listCustomers: "",
        setCustomer: "",
        removeCustomer: "",
        zones: "",
        recipients: "",
        telegram_chat_id: "",
      },
    };
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
    i18nTableColumns() {
      return this.tableColumns.map((column) =>
        this.$t("customers.col_" + column)
      );
    },
    locale() {
      return this.$i18n.locale;
    },
    zoneOptions() {
      return zoneOptions(
        this.countries,
        this.continents,
        this.locale,
        this.$t("customers.continent")
      );
    },
    recipientList() {
      return this.recipients.split(/[\s,;]+/).filter((r) => r !== "");
    },
  },
  created() {
    this.listCustomers();
    this.getConfiguration();
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
    openUrl(url) {
      window.open(url, "_blank", "noopener");
    },
    zoneText(zone) {
      return zoneLabel(
        zone,
        this.locale,
        this.continents,
        this.$t("customers.continent")
      );
    },
    isEmail(value) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    },
    showEditModal(customer) {
      this.clearErrors(this);
      this.customerToEdit = customer;
      this.zones = [...customer.zones];
      this.recipients = customer.recipients.join("\n");
      this.telegramEnabled = customer.telegram_enabled;
      this.telegramChatId = customer.telegram_chat_id;
      this.error.telegram_chat_id = "";
    },
    hideEditModal() {
      this.customerToEdit = null;
    },
    async listCustomers() {
      this.loading.listCustomers = true;
      this.error.listCustomers = "";
      const taskAction = "list-customers";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.listCustomersAborted
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.listCustomersCompleted
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
        this.error.listCustomers = this.getErrorMessage(err);
        this.loading.listCustomers = false;
      }
    },
    listCustomersAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.listCustomers = this.$t("error.generic_error");
      this.loading.listCustomers = false;
    },
    listCustomersCompleted(taskContext, taskResult) {
      this.customers = taskResult.output.customers;
      this.countries = taskResult.output.countries;
      this.continents = taskResult.output.continents;
      this.loading.listCustomers = false;
    },
    // Only to warn that the emails need the cluster smarthost, and Telegram the bot token
    async getConfiguration() {
      const taskAction = "get-configuration";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        (taskContext, taskResult) => {
          this.smarthostEnabled = taskResult.output.smarthost_enabled;
          this.telegramReady =
            taskResult.output.telegram_enabled &&
            taskResult.output.telegram_token_set;
        }
      );
      await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
    },
    validateSetCustomer() {
      this.clearErrors(this);
      if (this.recipientList.some((r) => !this.isEmail(r))) {
        this.error.recipients = "customers.recipients_invalid";
        this.focusElement("recipients");
        return false;
      }
      if (this.telegramEnabled && !CHAT_ID_PATTERN.test(this.telegramChatId)) {
        this.error.telegram_chat_id = this.telegramChatId
          ? "settings.telegram_chat_id_invalid"
          : "common.required";
        this.$refs.telegram_chat_id.focus();
        return false;
      }
      return true;
    },
    async setCustomer() {
      if (!this.validateSetCustomer()) {
        return;
      }
      this.loading.setCustomer = true;
      const taskAction = "set-customer";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.setCustomerAborted
      );
      this.core.$root.$once(
        `${taskAction}-validation-failed-${eventId}`,
        this.setCustomerValidationFailed
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.setCustomerCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data: {
            name: this.customerToEdit.name,
            zones: this.zones,
            recipients: [...new Set(this.recipientList)],
            telegram_enabled: this.telegramEnabled,
            telegram_chat_id: this.telegramChatId,
          },
          extra: {
            title: this.$t("customers.save_task", {
              name: this.customerToEdit.name,
            }),
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.setCustomer = this.getErrorMessage(err);
        this.loading.setCustomer = false;
      }
    },
    setCustomerAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.setCustomer = this.$t("error.generic_error");
      this.loading.setCustomer = false;
    },
    setCustomerValidationFailed(validationErrors) {
      this.loading.setCustomer = false;
      for (const e of validationErrors) {
        const key = e.parameter.split(".")[0];
        if (key in this.error) {
          this.error[key] = "customers." + e.error;
        } else {
          this.error.setCustomer = this.$t("customers." + e.error);
        }
      }
    },
    setCustomerCompleted() {
      this.loading.setCustomer = false;
      this.customerToEdit = null;
      this.listCustomers();
    },
    showRemoveModal(customer) {
      this.error.removeCustomer = "";
      this.customerToRemove = customer;
    },
    async removeCustomer() {
      this.loading.removeCustomer = true;
      this.error.removeCustomer = "";
      const taskAction = "remove-customer";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.removeCustomerAborted
      );
      this.core.$root.$once(
        `${taskAction}-validation-failed-${eventId}`,
        this.removeCustomerValidationFailed
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.removeCustomerCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data: { name: this.customerToRemove.name },
          extra: {
            title: this.$t("customers.remove_task", {
              name: this.customerToRemove.name,
            }),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.removeCustomer = this.getErrorMessage(err);
        this.loading.removeCustomer = false;
        this.customerToRemove = null;
      }
    },
    removeCustomerAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.removeCustomer = this.$t("error.generic_error");
      this.loading.removeCustomer = false;
      this.customerToRemove = null;
    },
    removeCustomerValidationFailed(validationErrors) {
      this.loading.removeCustomer = false;
      this.customerToRemove = null;
      // A schema error has no message of its own
      this.error.removeCustomer = validationErrors
        .map((e) =>
          this.$te("customers." + e.error)
            ? this.$t("customers." + e.error)
            : this.$t("error.generic_error")
        )
        .join(" ");
      this.listCustomers();
    },
    removeCustomerCompleted() {
      this.loading.removeCustomer = false;
      this.customerToRemove = null;
      this.listCustomers();
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
.mg-bottom {
  margin-bottom: $spacing-06;
}

.toolbar {
  margin-bottom: $spacing-05;
}
.muted {
  color: $text-02;
}
</style>
