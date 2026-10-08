<!--
  Copyright (C) 2026 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <cv-grid fullWidth>
    <cv-row>
      <cv-column class="page-title">
        <h2>{{ $t("agents.title") }}</h2>
      </cv-column>
    </cv-row>
    <cv-row v-if="error.removeAgent">
      <cv-column>
        <NsInlineNotification
          kind="error"
          :title="$t('action.remove-agent')"
          :description="error.removeAgent"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column class="toolbar">
        <NsButton
          kind="ghost"
          :icon="Restart20"
          :loading="loading.listAgents"
          :disabled="loading.listAgents"
          @click="listAgents"
          >{{ $t("agents.refresh") }}</NsButton
        >
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <cv-tile light>
          <NsDataTable
            :allRows="agents"
            :columns="i18nTableColumns"
            :rawColumns="tableColumns"
            :sortable="true"
            :pageSizes="[10, 25, 50, 100]"
            :overflow-menu="true"
            :isSearchable="agents.length > 10"
            :searchPlaceholder="$t('agents.search_agents')"
            :searchClearLabel="core.$t('common.clear_search')"
            :noSearchResultsLabel="core.$t('common.no_search_results')"
            :noSearchResultsDescription="
              core.$t('common.no_search_results_description')
            "
            :isLoading="loading.listAgents"
            :skeletonRows="3"
            :isErrorShown="!!error.listAgents"
            :errorTitle="$t('action.list-agents')"
            :errorDescription="error.listAgents"
            :itemsPerPageLabel="core.$t('pagination.items_per_page')"
            :rangeOfTotalItemsLabel="core.$t('pagination.range_of_total_items')"
            :ofTotalPagesLabel="core.$t('pagination.of_total_pages')"
            :backwardText="core.$t('pagination.previous_page')"
            :forwardText="core.$t('pagination.next_page')"
            :pageNumberLabel="core.$t('pagination.page_number')"
            @updatePage="tablePage = $event"
          >
            <template slot="empty-state">
              <NsEmptyState :title="$t('agents.no_agents')" />
            </template>
            <template slot="data">
              <cv-data-table-row
                v-for="(row, rowIndex) in tablePage"
                :key="`${rowIndex}`"
                :value="`${rowIndex}`"
              >
                <cv-data-table-cell>{{ row.name }}</cv-data-table-cell>
                <cv-data-table-cell>{{ row.ip || "-" }}</cv-data-table-cell>
                <cv-data-table-cell>
                  <NsTag
                    :label="statusLabel(row.status)"
                    :kind="statusKind(row.status)"
                  />
                </cv-data-table-cell>
                <cv-data-table-cell>{{
                  row.version || "-"
                }}</cv-data-table-cell>
                <cv-data-table-cell>{{ row.os || "-" }}</cv-data-table-cell>
                <cv-data-table-cell>{{
                  formatDateTime(row.last_keep_alive)
                }}</cv-data-table-cell>
                <cv-data-table-cell class="table-overflow-menu-cell">
                  <NsButton
                    kind="danger-tertiary"
                    size="small"
                    :icon="TrashCan20"
                    @click="showRevokeModal(row)"
                    >{{ $t("agents.revoke") }}</NsButton
                  >
                </cv-data-table-cell>
              </cv-data-table-row>
            </template>
          </NsDataTable>
        </cv-tile>
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column class="page-subtitle">
        <h4>{{ $t("agents.add_title") }}</h4>
      </cv-column>
    </cv-row>
    <cv-row v-if="error.getEnrollmentToken">
      <cv-column>
        <NsInlineNotification
          kind="error"
          :title="$t('action.get-enrollment-token')"
          :description="error.getEnrollmentToken"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column :md="4" :max="6">
        <cv-tile light>
          <p class="mg-bottom">{{ $t("agents.how_it_works") }}</p>
          <cv-form @submit.prevent="getEnrollmentToken">
            <NsTextInput
              v-model.trim="ttl"
              :label="$t('agents.ttl')"
              placeholder="1h"
              :helper-text="$t('agents.ttl_helper')"
              :invalid-message="$t(error.ttl)"
              :disabled="loading.getEnrollmentToken"
              class="mg-bottom"
              ref="ttl"
            />
            <NsTextInput
              v-model.trim="maxUses"
              :label="$t('agents.max_uses')"
              placeholder="1"
              :helper-text="$t('agents.max_uses_helper')"
              :invalid-message="$t(error.max_uses)"
              :disabled="loading.getEnrollmentToken"
              class="mg-bottom"
              ref="max_uses"
            />
            <NsTextInput
              v-model.trim="description"
              :label="$t('agents.description')"
              :disabled="loading.getEnrollmentToken"
              class="mg-bottom"
              ref="description"
            />
            <NsButton
              kind="primary"
              :icon="Add20"
              :loading="loading.getEnrollmentToken"
              :disabled="loading.getEnrollmentToken"
            >
              {{ $t("agents.create_token") }}
            </NsButton>
          </cv-form>
        </cv-tile>
      </cv-column>
      <cv-column :md="4" :max="10" v-if="result">
        <cv-tile light>
          <h4 class="mg-bottom">{{ $t("agents.token_ready") }}</h4>
          <p class="mg-bottom">
            {{
              $t("agents.token_expires", {
                date: formatDateTime(result.expires),
              })
            }}
          </p>
          <div class="mg-bottom-sm">{{ $t("agents.linux_command") }}</div>
          <NsCodeSnippet
            :copyTooltip="$t('agents.copy')"
            :copyFeedback="$t('agents.copied')"
            :feedbackAriaLabel="$t('agents.copied')"
            :moreText="$t('agents.show_more')"
            :lessText="$t('agents.show_less')"
            :wrapText="true"
            class="mg-bottom"
            >{{ installCommand }}</NsCodeSnippet
          >
          <p class="mg-bottom">{{ $t("agents.linux_hint") }}</p>
          <div class="mg-bottom-sm">{{ $t("agents.container_hint") }}</div>
          <NsCodeSnippet
            :copyTooltip="$t('agents.copy')"
            :copyFeedback="$t('agents.copied')"
            :feedbackAriaLabel="$t('agents.copied')"
            :moreText="$t('agents.show_more')"
            :lessText="$t('agents.show_less')"
            :wrapText="true"
            class="mg-bottom"
            >WAZUH_ENROLLMENT_TOKEN={{ result.token }}</NsCodeSnippet
          >
          <NsInlineNotification
            kind="info"
            :title="$t('agents.other_systems_title')"
            :description="$t('agents.other_systems')"
            :showCloseButton="false"
          />
        </cv-tile>
      </cv-column>
    </cv-row>
    <NsDangerDeleteModal
      :isShown="isShownRevokeModal"
      :name="agentToRevoke ? agentToRevoke.name : ''"
      :title="$t('agents.revoke_title')"
      :warning="$t('agents.revoke_warning')"
      :description="$t('agents.revoke_description')"
      :typeToConfirm="
        $t('agents.revoke_type_to_confirm', {
          name: agentToRevoke ? agentToRevoke.name : '',
        })
      "
      :deleteLabel="$t('agents.revoke')"
      :cancelLabel="core.$t('common.cancel')"
      :loading="loading.removeAgent"
      @hide="hideRevokeModal"
      @confirmDelete="removeAgent"
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

// Public place of the enrollment script of the module
const AGENT_SCRIPT_URL =
  "https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh";

export default {
  name: "Agents",
  mixins: [
    TaskService,
    IconService,
    UtilService,
    QueryParamService,
    PageTitleService,
  ],
  pageTitle() {
    return this.$t("agents.title") + " - " + this.appName;
  },
  data() {
    return {
      q: {
        page: "agents",
      },
      urlCheckInterval: null,
      agents: [],
      tablePage: [],
      tableColumns: [
        "name",
        "ip",
        "status",
        "version",
        "os",
        "last_keep_alive",
      ],
      ttl: "1h",
      maxUses: "1",
      description: "",
      result: null,
      isShownRevokeModal: false,
      agentToRevoke: null,
      loading: {
        listAgents: false,
        getEnrollmentToken: false,
        removeAgent: false,
      },
      error: {
        listAgents: "",
        removeAgent: "",
        getEnrollmentToken: "",
        ttl: "",
        max_uses: "",
      },
    };
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
    i18nTableColumns() {
      return this.tableColumns.map((column) => {
        return this.$t("agents.col_" + column);
      });
    },
    // The token goes through the environment so it does not show in the process list
    installCommand() {
      return `curl -fsSL ${AGENT_SCRIPT_URL} | sudo WAZUH_ENROLLMENT_TOKEN='${this.result.token}' bash`;
    },
  },
  created() {
    this.listAgents();
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
    statusKind(status) {
      if (status === "active") {
        return "green";
      }
      if (status === "disconnected") {
        return "red";
      }
      return "gray";
    },
    statusLabel(status) {
      const key = "agents.status_" + status;
      return this.$te(key) ? this.$t(key) : status;
    },
    formatDateTime(value) {
      if (!value) {
        return "-";
      }
      const date = new Date(value);
      return isNaN(date.getTime()) ? value : date.toLocaleString();
    },
    async listAgents() {
      this.loading.listAgents = true;
      this.error.listAgents = "";
      const taskAction = "list-agents";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.listAgentsAborted
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.listAgentsCompleted
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
        this.error.listAgents = this.getErrorMessage(err);
        this.loading.listAgents = false;
      }
    },
    listAgentsAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.listAgents = this.$t("error.generic_error");
      this.loading.listAgents = false;
    },
    listAgentsCompleted(taskContext, taskResult) {
      this.agents = taskResult.output.agents;
      this.loading.listAgents = false;
    },
    showRevokeModal(agent) {
      this.agentToRevoke = agent;
      this.isShownRevokeModal = true;
    },
    hideRevokeModal() {
      this.isShownRevokeModal = false;
    },
    async removeAgent() {
      this.loading.removeAgent = true;
      this.error.removeAgent = "";
      const taskAction = "remove-agent";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.removeAgentAborted
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.removeAgentCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data: { id: this.agentToRevoke.id },
          extra: {
            title: this.$t("agents.revoke_task", {
              name: this.agentToRevoke.name,
            }),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.removeAgent = this.getErrorMessage(err);
        this.loading.removeAgent = false;
        this.hideRevokeModal();
      }
    },
    removeAgentAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.removeAgent = this.$t("error.generic_error");
      this.loading.removeAgent = false;
      this.hideRevokeModal();
    },
    removeAgentCompleted() {
      this.loading.removeAgent = false;
      this.hideRevokeModal();
      this.listAgents();
    },
    validate() {
      this.clearErrors(this);
      let isValidationOk = true;
      if (!/^[0-9]+[smhd]$/.test(this.ttl)) {
        this.error.ttl = "agents.ttl_invalid";
        this.focusElement("ttl");
        isValidationOk = false;
      }
      if (!/^[1-9][0-9]*$/.test(this.maxUses)) {
        this.error.max_uses = "agents.max_uses_invalid";
        if (isValidationOk) {
          this.focusElement("max_uses");
        }
        isValidationOk = false;
      }
      return isValidationOk;
    },
    async getEnrollmentToken() {
      if (!this.validate()) {
        return;
      }
      this.loading.getEnrollmentToken = true;
      this.result = null;
      const taskAction = "get-enrollment-token";
      const eventId = this.getUuid();
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.getEnrollmentTokenAborted
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.getEnrollmentTokenCompleted
      );
      const data = { ttl: this.ttl, max_uses: parseInt(this.maxUses, 10) };
      if (this.description) {
        data.description = this.description;
      }
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data,
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
        this.error.getEnrollmentToken = this.getErrorMessage(err);
        this.loading.getEnrollmentToken = false;
      }
    },
    getEnrollmentTokenAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.getEnrollmentToken = this.$t("error.generic_error");
      this.loading.getEnrollmentToken = false;
    },
    getEnrollmentTokenCompleted(taskContext, taskResult) {
      this.result = taskResult.output;
      this.loading.getEnrollmentToken = false;
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
.mg-bottom {
  margin-bottom: $spacing-06;
}
.mg-bottom-sm {
  margin-bottom: $spacing-03;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: $spacing-03;
}
</style>
