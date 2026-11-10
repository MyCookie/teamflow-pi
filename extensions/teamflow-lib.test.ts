/**
 * Tests for extensions/teamflow-lib.ts (docs/extension-spec.md, Part 1).
 *
 * Run with: node --test extensions/teamflow-lib.test.ts
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { appendManagerPrompt, pathWithBin, spawnDecision } from "./teamflow-lib.ts";

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

// Part 3 (D3) — spawnDecision

const LEADS = ["research-lead", "impl-lead", "review-lead"];

function assertRefusalNamesLeads(reason: string) {
	for (const lead of LEADS) assert.ok(reason.includes(lead), `reason must name ${lead}: ${reason}`);
}

test("spawnDecision: a child session is allowed", () => {
	// Even for a non-lead agent: the leads' own allowedAgents limit them.
	assert.equal(spawnDecision({ agent: "implementer", task: "x" }, true), undefined);
});

test("spawnDecision: main session may launch research-lead", () => {
	assert.equal(spawnDecision({ agent: "research-lead", task: "x" }, false), undefined);
});

test("spawnDecision: main session may launch impl-lead", () => {
	assert.equal(spawnDecision({ agent: "impl-lead", task: "x" }, false), undefined);
});

test("spawnDecision: main session may launch review-lead", () => {
	assert.equal(spawnDecision({ agent: "review-lead", task: "x" }, false), undefined);
});

test("spawnDecision: main session may resume", () => {
	assert.equal(spawnDecision({ action: "resume", id: "run-1" }, false), undefined);
});

test("spawnDecision: main session refuses a non-lead agent", () => {
	const reason = spawnDecision({ agent: "implementer", task: "x" }, false);
	assert.ok(typeof reason === "string");
	assertRefusalNamesLeads(reason);
});

test("spawnDecision: main session refuses a lead inside tasks", () => {
	const reason = spawnDecision({ tasks: [{ agent: "impl-lead", task: "x" }] }, false);
	assert.ok(typeof reason === "string");
	assertRefusalNamesLeads(reason);
});

test("spawnDecision: main session refuses a missing agent", () => {
	const reason = spawnDecision({ task: "x" }, false);
	assert.ok(typeof reason === "string");
	assertRefusalNamesLeads(reason);
});

test("spawnDecision: main session refuses a lead with a chain", () => {
	const reason = spawnDecision(
		{ agent: "impl-lead", task: "x", chain: [{ agent: "implementer", task: "y" }] },
		false,
	);
	assert.ok(typeof reason === "string");
	assertRefusalNamesLeads(reason);
});
