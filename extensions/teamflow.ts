/**
 * teamflow-pi extension (docs/extension-spec.md).
 *
 * This file only wires pieces to Pi; the logic lives in ./teamflow-lib.ts.
 *
 * Part 1 (D4): replace the bash tool with one whose commands run with the
 * package's bin/ first on PATH, so agents find `tf`.
 * Part 3 (D3): with --teamflow, register the teamflow capability ceiling for
 * the session and gate the main session's `subagent` launches to the three
 * leads.
 *
 * Pattern copied from PD/examples/extensions/bash-spawn-hook.ts; package
 * root from PD/examples/extensions/doom-overlay/wad-finder.ts:7.
 */

import { createBashTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
	registerSubagentCapabilityCeiling,
	type SubagentCapabilityCeilingHandle,
} from "pi-subagents/capability-ceiling";

import { appendManagerPrompt, pathWithBin, spawnDecision } from "./teamflow-lib.ts";

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const binDir = join(packageRoot, "bin");
const managerPath = join(packageRoot, "manager.md");

// Part 3 (D3): the ten teamflow subagents — teamflow's agents/ minus manager
// (the main session). Canonical names are namespaced: agent frontmatter sets
// `package: teamflow`, so each registers as teamflow.<name> (Phase 4, human
// decision — avoids shadowing pi-subagents' builtin `researcher`).
const TEAMFLOW_AGENTS = [
	"teamflow.architect-reviewer",
	"teamflow.docs-reviewer",
	"teamflow.impl-lead",
	"teamflow.implementer",
	"teamflow.quality-reviewer",
	"teamflow.research-lead",
	"teamflow.researcher",
	"teamflow.review-lead",
	"teamflow.security-reviewer",
	"teamflow.simplicity-reviewer",
];

export default function (pi: ExtensionAPI) {
	const cwd = process.cwd();

	const bashTool = createBashTool(cwd, {
		spawnHook: ({ command, cwd, env }) => ({
			command,
			cwd,
			env: { ...env, PATH: pathWithBin(env.PATH, binDir) },
		}),
	});

	pi.registerTool({
		...bashTool,
		execute: async (id, params, signal, onUpdate, _ctx) => {
			return bashTool.execute(id, params, signal, onUpdate);
		},
	});

	// Part 2 (D3): --teamflow makes the main session the manager.
	// The flag is read in the handler, not the factory, where getFlag
	// still returns the default (PD/docs/extensions.md:1862-1880).
	pi.registerFlag("teamflow", {
		description: "Start as the teamflow manager",
		type: "boolean",
		default: false,
	});

	pi.on("before_agent_start", (event) => {
		if (!pi.getFlag("teamflow")) return;
		const manager = readFileSync(managerPath, "utf8");
		return {
			systemPrompt: appendManagerPrompt(event.systemPrompt, manager),
		};
	});

	// Part 3 (D3): the capability ceiling covers the whole agent tree.
	// Registered with the session id (PS/docs/extension-api.md:413-445);
	// pi-subagents imported as an npm dependency shares its registry with
	// Pi's installed copy in this process (Symbol.for, verified in
	// docs/spikes.md).
	let ceiling: SubagentCapabilityCeilingHandle | undefined;

	pi.on("session_start", (_event, ctx) => {
		if (!pi.getFlag("teamflow")) return;
		ceiling?.dispose();
		ceiling = registerSubagentCapabilityCeiling({
			sessionId: ctx.sessionManager.getSessionId(),
			source: "teamflow",
			ceiling: { allowedAgents: TEAMFLOW_AGENTS },
		});
	});

	pi.on("session_shutdown", () => {
		ceiling?.dispose();
		ceiling = undefined;
	});

	// Part 3 (D3): the main session may only spawn the three leads. Shape
	// from PD/examples/extensions/permission-gate.ts:13-33 — { block, reason }
	// refuses, undefined allows.
	pi.on("tool_call", (event) => {
		if (!pi.getFlag("teamflow") || event.toolName !== "subagent") return;
		const reason = spawnDecision(
			event.input as Record<string, unknown>,
			process.env.PI_SUBAGENT_CHILD === "1",
		);
		if (reason) return { block: true, reason };
	});
}
