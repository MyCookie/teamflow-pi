/**
 * teamflow-pi pure logic (docs/extension-spec.md).
 *
 * No Pi imports here — every function in this file must stay testable with
 * plain `node --test extensions/teamflow-lib.test.ts`.
 */

/**
 * Part 1 (D4): prepend `bin` to the old PATH, or return just `bin` when the
 * old PATH is empty or undefined.
 */
export function pathWithBin(path: string | undefined, bin: string): string {
	return path ? `${bin}:${path}` : bin;
}

/**
 * Part 2 (D3): the system prompt, two newlines, then the manager text.
 */
export function appendManagerPrompt(
	systemPrompt: string,
	manager: string,
): string {
	return `${systemPrompt}\n\n${manager}`;
}

// Part 3 (D3): the three leads the manager may launch.
const LEADS = ["research-lead", "impl-lead", "review-lead"];

/**
 * Part 3 (D3): refuse a main-session `subagent` call, or allow it.
 *
 * Returns a refusal reason (the extension blocks the call with it), or
 * `undefined` to allow:
 *
 * - child sessions are allowed (`isChild` true — they carry
 *   `PI_SUBAGENT_CHILD=1`; the leads' own `allowedAgents` limit them);
 * - the main session may launch a lead, with no `tasks` or `chain` field;
 * - `action: "resume"` is allowed (the manager resumes impl-lead);
 * - everything else is refused, naming the three leads. Fails closed: other
 *   subagent forms (parallel tasks, workflows, other actions) stay refused
 *   until a spike shows the manager needs one.
 */
export function spawnDecision(
	input: Record<string, unknown>,
	isChild: boolean,
): string | undefined {
	if (isChild) return undefined;
	if (input.action === "resume") return undefined;
	if (
		typeof input.agent === "string" &&
		LEADS.includes(input.agent) &&
		!("tasks" in input) &&
		!("chain" in input)
	) {
		return undefined;
	}
	return `The teamflow manager may only launch the leads: ${LEADS.join(
		",",
	)}.`;
}
