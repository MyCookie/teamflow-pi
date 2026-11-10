#!/usr/bin/env python3
"""A stand-in for the `gh` subcommands tf uses, for tests only.

State lives in the JSON file $FAKE_GH_STATE. $FAKE_GH_BARE points at a bare
repository that plays GitHub's copy of the branches; tests place it under a
directory named github.com/<owner>/<repo>.git so the path also satisfies
tf's GitHub-remote check. $FAKE_GH_LOGGED_OUT makes `gh auth status` fail.

State keys:
  prs         {n: {title, body, headRefName, baseRefName, state, files,
                   mergeStateStatus, [oid], [auto_merge]}} — headRefOid is
                   read from the bare repository's branch, or from "oid"
                   when the entry sets one (to play a head that moved)
  issues      {n: {title, body, labels, state, comments}}
  statuses    {sha: [{context, state, description}, ...]}
  checks      {n: {required: [...], all: [...]}} — check objects carry
                   name, bucket, plus any of state, workflow, event, link,
                   startedAt, completedAt, description; `pr checks --json`
                   answers only the fields asked for
  check_seq   {sha: [bucket, ...]} — consumed one bucket per `pr checks`
                   call; the last stays, as a finishing run does
  required    bool — `pr checks --required` answers the default gate check
                   (passing) when checks.n.required is not set
  rule_contexts [context, ...] — what the branch rules API requires; the
                   default when "required" is set is gate and
                   teamflow/code-review, else no rules at all
  rules_error  -> the branch rules API fails with an HTTP 500
  checks_error  -> every `pr checks` call fails with an HTTP 502
  checks_none  -> `pr checks` answers with no checks reported
  revoke_on_pending  -> a `pr checks` answer holding a pending check also
                   records a failure of the review status on the head, as
                   a reviewer rejecting it meanwhile would
  change_on_pending  {field: value} — a `pr checks` answer holding a
                   pending check also sets those PR fields, as a push, a
                   retarget or a close would
  reads       {required: n, all: m} — counters, for assertions
  merges      [argv, ...] — every `pr merge` call
  reviews     [argv, ...] — every `pr review` call
"""

import json
import os
import subprocess
import sys

STATUS = "teamflow/code-review"
STATE = os.environ["FAKE_GH_STATE"]
BARE = os.environ.get("FAKE_GH_BARE", "")


def load():
    defaults = {"next_issue": 1, "next_pr": 1, "issues": {}, "prs": {},
                "statuses": {}, "checks": {}, "check_seq": {},
                "reads": {"required": 0, "all": 0},
                "merges": [], "reviews": []}
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    for key, value in defaults.items():
        state.setdefault(key, value)
    return state


def save(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def opt(args, name, many=False):
    out = []
    for i, a in enumerate(args[:-1]):
        if a == name:
            out.append(args[i + 1])
    return out if many else (out[0] if out else None)


def slug_from(args):
    r = opt(args, "-R")
    if r:
        return r
    for a in args:
        if a.startswith("repos/") and "/" in a[6:]:
            return a[6:].split("/")[0]
    return "me/repo"


def head_of(state, pr):
    if pr.get("oid"):
        return pr["oid"]
    if BARE:
        result = subprocess.run(["git", "-C", BARE, "rev-parse",
                                 f"refs/heads/{pr['headRefName']}"],
                                text=True, capture_output=True)
        if result.returncode == 0:
            return result.stdout.strip()
    return ""


def full_pr(state, pr):
    return {
        "title": pr["title"],
        "body": pr["body"],
        "headRefName": pr["headRefName"],
        "headRefOid": head_of(state, pr),
        "baseRefName": pr["baseRefName"],
        "state": pr["state"],
        "files": [{"path": p} for p in pr.get("files", [])],
        "mergeStateStatus": pr.get("mergeStateStatus", "CLEAN"),
        "autoMergeRequest": ({"enabledAt": "2026-01-01T00:00:00Z"}
                             if pr.get("auto_merge") else None),
    }


def pr_checks(state, args):
    n = args[2]
    required = "--required" in args
    state["reads"]["required" if required else "all"] += 1
    if required and state.get("required_errors_left"):
        state["required_errors_left"] -= 1
        save(state)
        print("HTTP 503 Service Unavailable", file=sys.stderr)
        sys.exit(1)
    if state.get("checks_error"):
        print("HTTP 502 Bad Gateway", file=sys.stderr)
        sys.exit(1)
    entry = state.get("checks", {}).get(n, {})
    if required:
        if not state.get("required") and "required" not in entry:
            print("no required checks reported", file=sys.stderr)
            sys.exit(1)
        checks = entry.get("required", [{"name": "gate", "bucket": "pass"}])
    else:
        checks = entry.get("all", [{"name": "gate", "bucket": "pass"}])
    if state.get("checks_none"):
        print("no checks reported for this commit", file=sys.stderr)
        sys.exit(1)
    pr = state["prs"][n]
    seq = state.get("check_seq", {}).get(head_of(state, pr), [])
    if seq:
        if len(seq) > 1:
            state["check_seq"][head_of(state, pr)] = seq[1:]
        bucket = seq[0]
        checks = [dict(c) for c in checks]
        for c in checks:
            if c["name"] == "gate":
                c["bucket"] = bucket
    fields = opt(args, "--json").split(",")
    answered = [{f: c.get(f, "") for f in fields} for c in checks]
    if (state.get("revoke_on_pending") or state.get("change_on_pending")) \
            and any(c["bucket"] == "pending" for c in answered):
        if state.get("revoke_on_pending"):
            state["statuses"].setdefault(head_of(state, pr), []).insert(0,
                {"context": STATUS, "state": "failure",
                 "description": "REQUEST_CHANGES by teamflow:review-lead"})
        for key, value in (state.get("change_on_pending") or {}).items():
            state["prs"][n][key] = value
    print(json.dumps(answered))
    save(state)
    sys.exit(8 if any(c["bucket"] == "pending" for c in answered) else 0)


def main():
    args = sys.argv[1:]
    state = load()
    state["last_args"] = args
    save(state)

    if args[:2] == ["auth", "status"]:
        sys.exit(1 if os.environ.get("FAKE_GH_LOGGED_OUT") else 0)

    if args[0] == "issue":
        verb = args[1]
        if verb == "create":
            n = str(state["next_issue"])
            state["next_issue"] += 1
            state["issues"][n] = {
                "title": opt(args, "--title"),
                "body": opt(args, "--body"),
                "labels": opt(args, "--label", many=True) or [],
                "state": "open",
                "comments": [],
            }
            save(state)
            print(f"https://github.com/{slug_from(args)}/issues/{n}")
            sys.exit(0)
        elif verb == "list":
            wanted = []
            search = opt(args, "--search")
            if search and search.startswith("label:"):
                wanted = search[len("label:"):].split('","')
                wanted = [w.strip('"') for w in wanted]
            rows = []
            for n, i in state["issues"].items():
                if i["state"] != "open":
                    continue
                if wanted and not (set(wanted) & set(i["labels"])):
                    continue
                rows.append({"number": int(n), "title": i["title"],
                             "labels": [{"name": l} for l in i["labels"]]})
            print(json.dumps(rows))
            sys.exit(0)
        elif verb == "view":
            i = state["issues"][args[2]]
            fields = opt(args, "--json").split(",")
            full = {"title": i["title"], "state": i["state"],
                    "labels": [{"name": l} for l in i["labels"]],
                    "body": i["body"],
                    "comments": [{"createdAt": "2026-01-01T00:00:00Z",
                                  **c} for c in i["comments"]]}
            print(json.dumps({f: full[f] for f in fields}))
            sys.exit(0)
        elif verb == "comment":
            i = state["issues"][args[2]]
            i["comments"].append({"body": opt(args, "--body")})
            save(state)
            print(f"https://github.com/{slug_from(args)}/issues/{args[2]}#issuecomment-1")
            sys.exit(0)
        elif verb == "edit":
            i = state["issues"][args[2]]
            i["labels"] = [l for l in i["labels"]
                           if l not in opt(args, "--remove-label", many=True) or []]
            i["labels"] = [l for l in i["labels"]] + \
                [l for l in dict.fromkeys(opt(args, "--add-label", many=True) or [])
                 if l not in i["labels"]]
            save(state)
            sys.exit(0)
        elif verb == "close":
            state["issues"][args[2]]["state"] = "closed"
            save(state)
            print(f"https://github.com/{slug_from(args)}/issues/{args[2]}")
            sys.exit(0)
        else:
            raise SystemExit(f"fake_gh: unknown issue verb {verb}")

    if args[0] == "pr":
        verb = args[1]
        if verb == "create":
            n = str(state["next_pr"])
            state["next_pr"] += 1
            state["prs"][n] = {"title": opt(args, "--title"),
                               "body": opt(args, "--body"),
                               "headRefName": opt(args, "--head"),
                               "baseRefName": opt(args, "--base"),
                               "state": "OPEN"}
            save(state)
            print(f"https://github.com/{slug_from(args)}/pull/{n}")
            sys.exit(0)
        elif verb == "list":
            rows = [{"number": int(n), "title": p["title"],
                     "headRefName": p["headRefName"],
                     "baseRefName": p["baseRefName"]}
                    for n, p in state["prs"].items() if p["state"] == "OPEN"]
            print(json.dumps(rows))
            sys.exit(0)
        elif verb == "view":
            fields = opt(args, "--json").split(",")
            print(json.dumps({f: full_pr(state, state["prs"][args[2]])[f]
                              for f in fields}))
            sys.exit(0)
        elif verb == "review":
            state["reviews"].append(args[2:])
            save(state)
            print(f"https://github.com/{slug_from(args)}/pull/{args[2]}#pullrequestreview-1")
            sys.exit(0)
        elif verb == "merge":
            state["merges"].append(args[2:])
            if "--auto" in args:
                state["prs"][args[2]]["auto_merge"] = True
            if state.get("merge_error"):
                print("HTTP 502 Bad Gateway", file=sys.stderr)
                sys.exit(1)
            save(state)
            sys.exit(0)
        elif verb == "checks":
            pr_checks(state, args)
        else:
            raise SystemExit(f"fake_gh: unknown pr verb {verb}")

    if args[0] == "api":
        rest = args[1:]
        if rest and rest[0] == "--method":
            rest = rest[2:]  # --method POST <url>
        url = rest[0]
        if url.endswith("/status"):
            sha = url.rsplit("/status", 1)[0].rsplit("/", 1)[1]
            print(json.dumps({"statuses": state["statuses"].get(sha, [])}))
            sys.exit(0)
        elif "/statuses/" in url:
            sha = url.rsplit("/", 1)[1]
            fields = {f.split("=", 1)[0]: f.split("=", 1)[1]
                      for f in opt(args, "-f", many=True)}
            state["statuses"].setdefault(sha, []).insert(0,
                {"context": fields["context"], "state": fields["state"],
                 "description": fields["description"]})
            save(state)
            print(json.dumps({"id": 1}))
            sys.exit(0)
        elif url.endswith("/issues") or "/issues/" in url:
            n = url.rsplit("/", 1)[-1]
            if n in state["prs"]:
                print(json.dumps({"number": int(n),
                                  "pull_request": {"url": f"https://github.com/{url.split('/')[2]}/pull/{n}"}}))
                sys.exit(0)
            elif n in state["issues"]:
                i = state["issues"][n]
                print(json.dumps({"number": int(n), "labels": i["labels"]}))
                sys.exit(0)
            else:
                print("HTTP 404 Not Found", file=sys.stderr)
                sys.exit(1)
        elif "/rules/branches/" in url:
            if state.get("rules_error"):
                print("HTTP 500 Server Error", file=sys.stderr)
                sys.exit(1)
            if "rule_contexts" in state:
                contexts = state["rule_contexts"]
            elif state.get("required"):
                contexts = ["gate", STATUS]
            else:
                contexts = []
            rules = []
            if contexts:
                rules.append({"type": "required_status_checks",
                              "parameters": {"required_status_checks":
                                             [{"context": c} for c in contexts]}})
            print(json.dumps(rules))
            sys.exit(0)
        else:
            raise SystemExit(f"fake_gh: unhandled api url {url}")

    raise SystemExit(f"fake_gh: unhandled {args}")


if __name__ == "__main__":
    main()
