/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// A group ID, a user ID or a public channel name, as the backend accepts it
export const CHAT_ID_PATTERN = /^(-?[0-9]+|@[A-Za-z0-9_]{5,32})$/;

// Checked before sending: a wrong token would come back in the validation error of the task
export const TOKEN_PATTERN = /^[0-9]+:[A-Za-z0-9_-]+$/;

// Run a Telegram action, or the test of another channel. Resolves with { output } when it worked,
// else with the parameter in fault ("token", "chat_id" or "") and a translated message.
export function runTelegramAction(vm, taskAction, data) {
  return new Promise((resolve) => {
    const eventId = vm.getUuid();
    vm.core.$root.$once(
      `${taskAction}-completed-${eventId}`,
      (taskContext, taskResult) => resolve({ output: taskResult.output })
    );
    vm.core.$root.$once(`${taskAction}-aborted-${eventId}`, () =>
      resolve({ parameter: "", message: vm.$t("error.generic_error") })
    );
    vm.core.$root.$once(
      `${taskAction}-validation-failed-${eventId}`,
      (errors) =>
        resolve({
          parameter: errors[0].parameter,
          message: vm.$t("settings." + errors[0].error),
        })
    );
    vm.createModuleTaskForApp(vm.instanceName, {
      action: taskAction,
      data,
      extra: {
        title: vm.$t("action." + taskAction),
        isNotificationHidden: true,
        eventId,
      },
    }).catch((err) =>
      resolve({ parameter: "", message: vm.getErrorMessage(err) })
    );
  });
}

export function testTelegram(vm, data) {
  return runTelegramAction(vm, "test-telegram", data);
}

export function listTelegramChats(vm, data) {
  return runTelegramAction(vm, "list-telegram-chats", data);
}
