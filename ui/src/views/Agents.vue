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
    <cv-row>
      <cv-column>
        <NsInlineNotification
          kind="info"
          :title="$t('agents.how_it_works_title')"
          :description="$t('agents.how_it_works')"
          :showCloseButton="false"
        />
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
            {{ $t("agents.token_expires", { date: expiresLabel }) }}
          </p>
          <div class="mg-bottom-sm">{{ $t("agents.server_address") }}</div>
          <NsCodeSnippet
            :copyTooltip="$t('agents.copy')"
            :copyFeedback="$t('agents.copied')"
            :feedbackAriaLabel="$t('agents.copied')"
            :wrapText="true"
            hideExpandButton
            class="mg-bottom"
            >{{ result.address }}</NsCodeSnippet
          >
          <div class="mg-bottom-sm">{{ $t("agents.token") }}</div>
          <NsCodeSnippet
            :copyTooltip="$t('agents.copy')"
            :copyFeedback="$t('agents.copied')"
            :feedbackAriaLabel="$t('agents.copied')"
            :moreText="$t('agents.show_more')"
            :lessText="$t('agents.show_less')"
            :wrapText="true"
            class="mg-bottom"
            >{{ result.token }}</NsCodeSnippet
          >
          <p class="mg-bottom">{{ $t("agents.container_hint") }}</p>
          <NsCodeSnippet
            :copyTooltip="$t('agents.copy')"
            :copyFeedback="$t('agents.copied')"
            :feedbackAriaLabel="$t('agents.copied')"
            :wrapText="true"
            hideExpandButton
            >WAZUH_ENROLLMENT_TOKEN={{ result.token }}</NsCodeSnippet
          >
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
      ttl: "1h",
      maxUses: "1",
      description: "",
      result: null,
      loading: {
        getEnrollmentToken: false,
      },
      error: {
        getEnrollmentToken: "",
        ttl: "",
        max_uses: "",
      },
    };
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
    expiresLabel() {
      return this.result ? new Date(this.result.expires).toLocaleString() : "";
    },
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
</style>
