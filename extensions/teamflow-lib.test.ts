/**
 * Tests for extensions/teamflow-lib.ts (docs/extension-spec.md, Part 1).
 *
 * Run with: node --test extensions/teamflow-lib.test.ts
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { pathWithBin } from "./teamflow-lib.ts";

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
