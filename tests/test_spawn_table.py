"""Spawn-table guard for the ten teamflow subagents in agents/.

The teamflow spawn table (docs/teamflow/agents.md "Spawn table"; workflow
skill, Handoffs) fixes exactly who may delegate to whom.  This test
parses the frontmatter of every agent file and fails if the table is
widened (a lead gains an extra allowedAgents entry) or if a worker is
given the subagent tool.  It also pins the harness decisions: namespaced
canonical names (package: teamflow), no model (D5), inherited project
context, the workflow skill on every agent, and the per-role tool
allowlists (researcher's web tools, implementer's edit/write, the
read-only reviewers, simplicity-reviewer's ponytail skills).

Run under the gate:  python3 -m unittest discover -s tests
"""

import os
import re
import unittest

AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents")

LEADS = {
    "research-lead": ["researcher"],
    "impl-lead": ["implementer"],
    "review-lead": [
        "architect-reviewer",
        "security-reviewer",
        "quality-reviewer",
        "docs-reviewer",
        "simplicity-reviewer",
    ],
}
NON_LEADS = [
    "researcher",
    "implementer",
    "architect-reviewer",
    "security-reviewer",
    "quality-reviewer",
    "docs-reviewer",
    "simplicity-reviewer",
]
ALL_NAMES = set(LEADS) | set(NON_LEADS)

REVIEWERS = [
    "architect-reviewer",
    "security-reviewer",
    "quality-reviewer",
    "docs-reviewer",
    "simplicity-reviewer",
]


def parse_frontmatter(path):
    """Return {key: value} for the single-line frontmatter of a .md file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm


def as_list(value):
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def agents():
    if not os.path.isdir(AGENTS_DIR):
        return {}
    return {
        name[:-3]: parse_frontmatter(os.path.join(AGENTS_DIR, name))
        for name in sorted(os.listdir(AGENTS_DIR))
        if name.endswith(".md")
    }


class SpawnTableTest(unittest.TestCase):
    def setUp(self):
        self.agents = agents()
        # Every role is present, no stray files.
        self.assertEqual(set(self.agents), ALL_NAMES,
                         "agent files present: %s" % sorted(self.agents))

    def frontmatter(self, name):
        fm = self.agents.get(name)
        self.assertIsNotNone(fm, "no frontmatter in agents/%s.md" % name)
        return fm

    def tools(self, name):
        return as_list(self.frontmatter(name).get("tools"))

    def allowed(self, name):
        return as_list(self.frontmatter(name).get("allowedAgents"))

    def skills(self, name):
        return as_list(self.frontmatter(name).get("skills"))

    def test_namespaced_canonical_names(self):
        for name in ALL_NAMES:
            fm = self.frontmatter(name)
            self.assertEqual(fm.get("name"), name,
                             "%s: name field must be '%s'" % (name, name))
            self.assertEqual(fm.get("package"), "teamflow",
                             "%s: package must be 'teamflow' so the canonical "
                             "name is 'teamflow.%s'" % (name, name))

    def test_no_model(self):
        for name in ALL_NAMES:
            fm = self.frontmatter(name)
            self.assertNotIn("model", fm,
                             "%s: must not set a model (D5)" % name)

    def test_inherit_project_context_and_workflow_skill(self):
        for name in ALL_NAMES:
            fm = self.frontmatter(name)
            self.assertEqual(fm.get("inheritProjectContext"), "true",
                             "%s: inheritProjectContext must be true" % name)
            self.assertIn("workflow", self.skills(name),
                          "%s: must carry the workflow skill" % name)

    def test_leads_can_only_spawn_their_table(self):
        for lead, table in LEADS.items():
            tools = self.tools(lead)
            self.assertIn("subagent", tools,
                          "%s: must have the subagent tool" % lead)
            got = {a.split(".")[-1] for a in self.allowed(lead)}
            want = set(table)
            self.assertEqual(got, want,
                             "%s: allowedAgents must be exactly %s, got %s "
                             "(widening the spawn table is a decision)"
                             % (lead, sorted(want), sorted(got)))

    def test_leads_use_namespaced_allowed_agents(self):
        for lead in LEADS:
            for agent in self.allowed(lead):
                self.assertTrue(agent.startswith("teamflow."),
                                "%s: allowedAgents entries must be namespaced "
                                "(teamflow.<name>), got '%s'" % (lead, agent))

    def test_workers_cannot_delegate(self):
        for name in NON_LEADS:
            tools = self.tools(name)
            self.assertNotIn("subagent", tools,
                             "%s: a worker must not have the subagent tool"
                             % name)
            self.assertEqual(self.allowed(name), [],
                             "%s: a worker must have no allowedAgents" % name)

    def test_researcher_has_web_tools(self):
        tools = self.tools("researcher")
        self.assertIn("web_search", tools, "researcher: needs web_search")
        self.assertIn("fetch_content", tools, "researcher: needs fetch_content")

    def test_implementer_may_edit_and_write(self):
        tools = self.tools("implementer")
        self.assertIn("edit", tools, "implementer: needs edit")
        self.assertIn("write", tools, "implementer: needs write")

    def test_reviewers_are_read_only(self):
        for name in REVIEWERS:
            tools = self.tools(name)
            self.assertNotIn("edit", tools, "%s: must be read-only" % name)
            self.assertNotIn("write", tools, "%s: must be read-only" % name)

    def test_simplicity_reviewer_carries_ponytail_skills(self):
        skills = self.skills("simplicity-reviewer")
        for want in ("ponytail", "ponytail-audit", "ponytail-debt"):
            self.assertIn(want, skills,
                          "simplicity-reviewer: must carry the '%s' skill (D6)"
                          % want)


class SpawnTableWideningIsRejectedTest(unittest.TestCase):
    """Prove the guard actually fails: a widened lead must be caught."""

    def test_widening_a_lead_is_detected(self):
        # Temporarily pretend research-lead may also spawn the implementer.
        original = parse_frontmatter(os.path.join(AGENTS_DIR, "research-lead.md"))
        self.assertIsNotNone(original)
        widened = {k: v for k, v in original.items()}
        widened["allowedAgents"] = (
            "teamflow.researcher, teamflow.implementer"
        )
        got = {a.split(".")[-1] for a in as_list(widened["allowedAgents"])}
        want = set(LEADS["research-lead"])
        self.assertNotEqual(got, want,
                            "the guard must reject a widened spawn table")


if __name__ == "__main__":
    unittest.main()
