<!--
  Copyright (C) 2026 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <div>
    <div class="chat-picker">
      <cv-dropdown
        v-if="!manual"
        :value="value"
        @change="$emit('input', $event)"
        :label="label"
        :placeholder="
          chats.length
            ? $t('settings.telegram_choose_chat')
            : $t('settings.telegram_click_find')
        "
        :invalid-message="chatError"
        :disabled="disabled || !chats.length"
        class="chat-field"
        ref="chat_id"
      >
        <cv-dropdown-item v-for="chat in chats" :key="chat.id" :value="chat.id"
          >{{ chat.title }} ({{
            $t("settings.telegram_chat_" + chat.type)
          }})</cv-dropdown-item
        >
      </cv-dropdown>
      <NsTextInput
        v-else
        :value="value"
        @input="$emit('input', $event.trim())"
        :label="label"
        placeholder="-1001234567890"
        :invalid-message="chatError"
        :disabled="disabled"
        class="chat-field"
        ref="chat_id"
      />
      <NsButton
        type="button"
        kind="tertiary"
        size="field"
        :loading="loading.list"
        :disabled="disabled || loading.list"
        @click="findChats(false)"
        class="side-button"
        >{{ $t("settings.telegram_find_chats") }}</NsButton
      >
    </div>
    <div class="chat-helper mg-bottom">
      {{ helper }}
      <cv-link @click="manual = !manual">{{
        manual
          ? $t("settings.telegram_pick_from_list")
          : $t("settings.telegram_type_id")
      }}</cv-link>
    </div>
    <NsInlineNotification
      v-if="noChats"
      kind="info"
      :title="$t('settings.telegram_no_chats_title')"
      :description="$t('settings.telegram_no_chats_description')"
      :showCloseButton="false"
    />
    <NsInlineNotification
      v-if="error.list"
      kind="error"
      :title="$t('action.list-telegram-chats')"
      :description="error.list"
      :showCloseButton="false"
    />
    <NsButton
      type="button"
      v-if="value"
      kind="secondary"
      size="field"
      :loading="loading.test"
      :disabled="disabled || loading.test"
      @click="sendTest"
      class="mg-bottom"
      >{{ $t("settings.telegram_test") }}</NsButton
    >
    <NsInlineNotification
      v-if="testSent"
      kind="success"
      :title="$t('settings.telegram_test_sent')"
      :showCloseButton="false"
    />
    <NsInlineNotification
      v-if="error.test"
      kind="error"
      :title="$t('action.test-telegram')"
      :description="error.test"
      :showCloseButton="false"
    />
  </div>
</template>

<script>
import { mapState } from "vuex";
import { UtilService, TaskService } from "@nethserver/ns8-ui-lib";
import {
  CHAT_ID_PATTERN,
  listTelegramChats,
  testTelegram,
} from "../lib/telegram";

// The chat field of Telegram, with the chats of the bot to pick from and a test message
export default {
  name: "TelegramChat",
  mixins: [UtilService, TaskService],
  props: {
    value: { type: String, default: "" },
    label: { type: String, required: true },
    helper: { type: String, default: "" },
    // A token typed but not saved yet: the lookups and the test use it
    token: { type: String, default: "" },
    disabled: { type: Boolean, default: false },
    // Set by the parent when the saved form refused the chat ID
    invalidMessage: { type: String, default: "" },
  },
  data() {
    return {
      chats: [],
      manual: false,
      noChats: false,
      testSent: false,
      // Bumped by each lookup: an answer that comes after a newer one is dropped
      lookup: 0,
      loading: { list: false, test: false },
      error: { chat: "", list: "", test: "" },
    };
  },
  computed: {
    ...mapState(["instanceName", "core"]),
    chatError() {
      return this.error.chat || this.invalidMessage;
    },
  },
  watch: {
    value() {
      this.testSent = false;
      this.error.chat = "";
      this.error.test = "";
    },
  },
  created() {
    // Only the saved chat is resolved here, to show its name: errors wait for a click
    if (this.value) {
      this.findChats(true);
    }
  },
  methods: {
    focus() {
      this.focusElement("chat_id");
    },
    async findChats(silent) {
      const lookup = ++this.lookup;
      this.noChats = false;
      this.error.list = "";
      this.loading.list = true;
      const data = CHAT_ID_PATTERN.test(this.value)
        ? { chat_ids: [this.value] }
        : {};
      if (this.token) {
        data.token = this.token;
      }
      const result = await listTelegramChats(this, data);
      if (lookup !== this.lookup) {
        return;
      }
      this.loading.list = false;
      if ("output" in result) {
        this.chats = result.output.chats;
        this.noChats = !silent && !this.chats.length;
      } else if (!silent) {
        this.error.list = result.message;
      }
      // A chat the bot cannot see stays editable instead of vanishing from the list
      this.manual =
        !!this.value && !this.chats.some((chat) => chat.id === this.value);
    },
    async sendTest() {
      this.testSent = false;
      this.error.test = "";
      this.error.chat = "";
      if (!CHAT_ID_PATTERN.test(this.value)) {
        this.error.chat = this.$t("settings.telegram_chat_id_invalid");
        this.focus();
        return;
      }
      this.loading.test = true;
      const data = { chat_id: this.value };
      if (this.token) {
        data.token = this.token;
      }
      const result = await testTelegram(this, data);
      this.loading.test = false;
      if ("output" in result) {
        this.testSent = true;
      } else if (result.parameter === "chat_id") {
        this.error.chat = result.message;
      } else {
        this.error.test = result.message;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
.mg-bottom {
  margin-bottom: $spacing-06;
}

.chat-picker {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: $spacing-05;
}

.chat-field {
  flex: 0 1 20rem;
}

// Level with the field, not with its label or its error below
.side-button {
  margin-top: $spacing-06;
}

.chat-helper {
  margin-top: $spacing-03;
  font-size: 0.75rem;
  color: $text-02;
}
</style>
