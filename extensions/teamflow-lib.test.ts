/**
 * Tests for extensions/teamflow-lib.ts (docs/extension-spec.md, Part 1).
 *
 * Run with: node --test extensions/teamflow-lib.test.ts
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { appendManagerPrompt, pathWithBin } from "./teamflow-lib.ts";

test("pathWithBin prepends bin to an existing PATH", () => {
	assert.equal(
		pathWithBin("/usr/local/bin:/usr/bin:/bin", "/pkg/bin"),
		"/pkg/bin:/usr/local/bin:/usr/bin:/bin",
	);
});

test("pathWithBin returns just bin when the old PATH is empty", () => {
	assert.equal(pathWithBin("", "/pkg/bin"), "/pkg/bin");
});

test("pathWithBin returns just bin when the old PATH is undefined", () => {
	assert.equal(pathWithBin(undefined, "/pkg/bin"), "/pkg/bin");
});

// Part 2 (D3)

test("appendManagerPrompt: result starts with the original and ends with the manager text", () => {
	const original = "You are a coding assistant.";
	const manager = "Your name is teamflow-manager.";
	const out = appendManagerPrompt(original, manager);
	assert.ok(out.startsWith(original));
	assert.ok(out.endsWith(manager));
	assert.equal(out, original + "\n\n" + manager);
});
