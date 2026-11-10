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
