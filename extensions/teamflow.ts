/**
 * teamflow-pi extension (docs/extension-spec.md).
 *
 * This file only wires pieces to Pi; the logic lives in ./teamflow-lib.ts.
 *
 * Part 1 (D4): replace the bash tool with one whose commands run with the
 * package's bin/ first on PATH, so agents find `tf`.
 *
 * Pattern copied from PD/examples/extensions/bash-spawn-hook.ts; package
 * root from PD/examples/extensions/doom-overlay/wad-finder.ts:7.
 */

import { createBashTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { pathWithBin } from "./teamflow-lib.ts";

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const binDir = join(packageRoot, "bin");

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
}
