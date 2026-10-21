/*
 * Copyright (C) 2026 Nethesis S.r.l.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

import { runTelegramAction } from "./telegram";

// The server, the conversation token and the bot secret as the backend accepts them
export const URL_PATTERN = /^https:\/\/[^/?#]+(\/[^?#]*)?$/;
export const CONVERSATION_PATTERN = /^[a-z0-9]{4,32}$/;
export const SECRET_PATTERN = /^[\x21-\x7e]{40,128}$/;

// Resolves with { output } when the message was posted, else with the
// parameter in fault ("url", "conversation", "secret" or "") and a translated message
export function testTalk(vm, data) {
  return runTelegramAction(vm, "test-talk", data);
}
