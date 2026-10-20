PILOT PACK: MULTI-DAY TEAM WORK (0.207.0 to 0.210.0)
STATUS: PREPARED, NOT RUN. There are no pilot results in this folder.

Purpose
  Run 3 teams for 3 to 7 days on a separate Jarvis 007 install to see whether three things hold up with a real model:
  1. Approval gate: a step that needs the owner really stops, and an outside action runs only as the exact approved call, once.
  2. Department mandate: the team finds work in its assigned sources on its own, within budget, without making things up, and leaves a trace.
  3. Acceptance: a job is done only when the product meets the owner's criteria.

Files
  README.txt              this file: overview and reading order
  run_guide.txt           how to run, daily monitoring, emergency stop and rollback
  scenarios.txt           7-day scenarios for the 3 teams, what the owner does each day
  limits.txt              provider and model, budget, limits, stop conditions
  metrics.txt             metrics and how to measure them (from data, not from agent claims)
  report_template.txt     report template to fill in AFTER the run (currently empty)
  requirements_matrix.txt requirement -> code -> test -> evidence
  config/teams.json       config for the 3 teams: members, permissions, mandate, sample acceptance criteria
  trace_export.py         exports the trace mandate -> opportunity -> decision -> approval -> job -> product -> acceptance (read-only)
  ui_narrow_check.mjs     checks the approval card, mandate and acceptance on a narrow 390px screen in Vietnamese and English

Pinned build
  Candidate: 7b90482177ef05635e4e628451b30a8610cbac50
  (the final code and test commit of 0.210.0 on branch claude/openmausbot-jarvis-research-ewnzc6; the commit after it only
  records this SHA in the docs). If PR #728 gets more code-fix commits before the run, pin the newest code commit and
  record it in report_template.txt. Do not run on main until the owner approves the PR.

Not part of this goal
  No merge, no real model calls, no pilot run, no deploy, no touching the VPS.
