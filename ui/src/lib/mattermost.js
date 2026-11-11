/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { runTelegramAction } from "./telegram";

// The webhook, the channel and the sender name as the backend accepts them
export const WEBHOOK_PATTERN =
  /^https:\/\/[^/?#]+(\/[^?#]*)?\/hooks\/[A-Za-z0-9]+$/;
export const CHANNEL_PATTERN = /^@?[a-z0-9._-]{1,64}$/;
export const USERNAME_PATTERN = /^[A-Za-z0-9 ._()-]{0,64}$/;

// Resolves with { output } when the message was posted, else with the
// parameter in fault ("webhook", "channel" or "") and a translated message
export function testMattermost(vm, data) {
  return runTelegramAction(vm, "test-mattermost", data);
}
