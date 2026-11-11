/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { runTelegramAction } from "./telegram";

// The server and the topic as the backend accepts them
export const URL_PATTERN = /^https:\/\/[^/?#]+(\/[^?#]*)?$/;
export const TOPIC_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
export const TOKEN_PATTERN = /^tk_[A-Za-z0-9]+$/;

// Resolves with { output } when the message was published, else with the
// parameter in fault ("url", "topic", "token" or "") and a translated message
export function testNtfy(vm, data) {
  return runTelegramAction(vm, "test-ntfy", data);
}
