<!--
  Copyright (C) 2026 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <NsModal
    size="default"
    kind="danger"
    :visible="visible"
    :isLoading="loading.restartModule"
    :primary-button-disabled="loading.restartModule"
    @modal-hidden="onModalHidden"
    @primary-click="restartModule"
  >
    <template slot="title">
      {{ core.$t("apps_status.restart_application") }}
    </template>
    <template slot="content">
      <p>
        {{ core.$t("software_center.restart_app", { name: appName }) }}
      </p>
      <NsInlineNotification
        v-if="error.restartModule"
        kind="error"
        :title="core.$t('action.restart-module')"
        :description="error.restartModule"
        :showCloseButton="false"
      />
    </template>
    <template slot="secondary-button">{{ core.$t("common.cancel") }}</template>
    <template slot="primary-button">{{
      core.$t("apps_status.restart_application")
    }}</template>
  </NsModal>
</template>

<script>
import to from "await-to-js";
import { mapState } from "vuex";
import { UtilService, TaskService, IconService } from "@nethserver/ns8-ui-lib";

export default {
  name: "RestartModuleModal",
  mixins: [UtilService, TaskService, IconService],
  props: {
    visible: {
      type: Boolean,
      required: true,
    },
    node: {
      // get-status returns it as a number
      type: [String, Number],
      default: "",
    },
  },
  data() {
    return {
      loading: { restartModule: false },
      error: { restartModule: "" },
    };
  },
  computed: {
    ...mapState(["instanceName", "instanceLabel", "core"]),
    appName() {
      return this.instanceLabel
        ? this.instanceLabel + " (" + this.instanceName + ")"
        : this.instanceName;
    },
  },
  methods: {
    async restartModule() {
      this.error.restartModule = "";
      this.loading.restartModule = true;
      const taskAction = "restart-module";
      const eventId = this.getUuid();

      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.restartModuleAborted
      );
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.restartModuleCompleted
      );

      // A node action from the core, not one of ours.
      const res = await to(
        this.createNodeTaskForApp(this.node, {
          action: taskAction,
          data: {
            module_id: this.instanceName,
          },
          extra: {
            title: this.core.$t("applications.restart_instance_name", {
              instance: this.instanceLabel || this.instanceName,
            }),
            description: this.core.$t("applications.restarting"),
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.restartModule = this.getErrorMessage(err);
        this.loading.restartModule = false;
        return;
      }
    },
    restartModuleAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.restartModule = this.$t("error.generic_error");
      this.loading.restartModule = false;
    },
    restartModuleCompleted() {
      this.loading.restartModule = false;
      this.$emit("hide");
    },
    onModalHidden() {
      this.clearErrors();
      this.$emit("hide");
    },
  },
};
</script>
