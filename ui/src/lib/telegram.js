/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

// A group ID, a user ID or a public channel name, as the backend accepts it
export const CHAT_ID_PATTERN = /^(-?[0-9]+|@[A-Za-z0-9_]{5,32})$/;

// Send a test message. Resolves with null when it arrived, else with the parameter
// in fault ("token", "chat_id" or "") and a translated message.
export function testTelegram(vm, data) {
  return new Promise((resolve) => {
    const taskAction = "test-telegram";
    const eventId = vm.getUuid();
    vm.core.$root.$once(`${taskAction}-completed-${eventId}`, () =>
      resolve(null)
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
