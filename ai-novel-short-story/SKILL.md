---
name: ai-novel-short-story
description: "Write or revise a complete 3,000–30,000-character Chinese web short story from an idea, with three-direction selection, a 2–8-segment causal plan, sequential drafting, one full audit, at most one necessary repair, and resumable file state. Use for short-story creation; do not use for long novels, screenplay/script formats, or atmosphere-only literary sketches."
metadata:
  source: "Adapted workflow from https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant"
---

# AI Novel Short Story

Create a complete Chinese commercial web short story that a reader can finish in one sitting. The story must preserve the user's core idea, use active causation, and reach a definite ending.

## Scope

- Short story target length is 3,000–30,000 non-whitespace characters.
- Treat internal segments only as production, recovery, and editing units. Final output is continuous prose without segment headings.
- Do not force an idea with a large character arc, multiple worlds, or an expensive ending into short form. Tell the user it is better suited to a long novel and stop.
- This skill writes web fiction, not screenplay formatting, a treatment, prose poetry, or a scene sketch.

## Persistent Project

Resolve the directory containing this `SKILL.md` and use its `scripts/story_state.py`.

Unless the user names a destination, create a project directory under the current workspace:

```text
<workspace>/short-story-<short-slug>/
```

The helper creates and maintains:

```text
state.json                 authoritative workflow state
directions.md              three proposed directions
plan.md                    readable segment and causal plan
segments/01.md ...         internal segment prose
story.md                   continuous reader-facing prose
review.md                  audit findings and repair record
```

Run `python <skill-dir>/scripts/story_state.py --help` if command details are unclear. Never overwrite an existing state file with `init`.

### Mandatory S1A entry

When this skill is used inside `short-video-flow`, every production must start at S1A before running:

```text
python <short-video-flow-dir>/scripts/check_sequence.py --dir <production-dir> --enter S1A
```

A user-supplied story does not skip S1A. In that case:

- preserve the original as `01-故事/source-original.md`;
- create or accept the reader-facing `01-故事/story.md`;
- record the source, allowed changes, review, and de-slop result in `01-故事/review.md`;
- require user confirmation before G1-A passes.

Do not hand the story to S1B or initialize a drama project from this skill.

## Workflow

### 1. Interpret the request

Extract the original idea, target reader, emotional experience, platform, tone, hard constraints, and forbidden outcomes.

Decide whether the material genuinely fits short form and choose a target word count in the allowed range. Explain the recommendation in one or two sentences. If the user supplied a target or platform, preserve it.

Use a generic Chinese commercial web-fiction profile when no platform is specified. Do not block the workflow merely because the platform is unknown.

For details about form selection and platform behavior, read [references/workflow.md](references/workflow.md#1-interpret-and-route).

### 2. Propose three distinct directions

Generate exactly three directions that can each carry the target length. Differences must appear in the core experience, conflict engine, or ending payoff, not only names and titles.

Each direction needs:

- `id`, `title`, `premise`
- `core_experience`
- `protagonist`
- `central_conflict`
- `ending_promise`
- `style_keywords`

Write the interpretation and all three directions to a temporary JSON file, then save them:

```text
python <skill-dir>/scripts/story_state.py set-directions <project-dir> --input <directions.json>
```

Show all three directions to the user in concise prose and ask which one to use. If the user explicitly says to choose for them, select the strongest option and continue without another round.

Select the direction with:

```text
python <skill-dir>/scripts/story_state.py choose-direction <project-dir> --id <id>
```

The direction JSON contract is in [references/workflow.md](references/workflow.md#2-directions).

### 3. Build the causal plan

Plan 2–8 internal segments according to causal turns, not arbitrary equal word blocks.

Create a `causalContract` before prose:

- one protagonist goal;
- one central dramatic question;
- at least three fixed facts;
- a cause-and-effect chain from the opening pressure to the ending;
- at least two setup/payoff pairs.

Every key solution, identity, rule, resource, or rescue must be discoverable before it solves the climax. Do not add an unplanted exception at the end.

Each segment must specify its target length, opening state and hook, immediate goal, 2–6 causal beats, turning point, genre-compatible payoff, closing pull, and closing state. The final segment must fulfill `endingPromise`.

Save the plan with:

```text
python <skill-dir>/scripts/story_state.py set-plan <project-dir> --input <plan.json>
```

Use the schema and planning guidance in [references/workflow.md](references/workflow.md#3-plan).

### 4. Draft sequentially

Write one segment at a time, in order. Before each segment:

1. Read `plan.md`, `state.json`, `story.md`, and the previous segment's continuity summary.
2. Write only the current segment's opening hook, goal, causal beats, turn, payoff, pull, and closing state.
3. Treat the causal contract as immutable unless the user explicitly approves a change.
4. Do not output segment headings, chapter numbers, planning notes, or Markdown inside prose.
5. End the last segment with a concrete climax and resolution. A suggestive final image is allowed only after the story question is answered.

Save each result from a JSON file containing `content` and `continuity_summary`:

```text
python <skill-dir>/scripts/story_state.py save-segment <project-dir> --order 1 --input <segment.json>
```

The helper rebuilds `story.md`. If a segment already exists, use `edit-segment` only for a user-directed edit:

```text
python <skill-dir>/scripts/story_state.py edit-segment <project-dir> --order 1 --input <segment.json> --human
```

Never use `--replace-human` without explicit user consent.

### 5. Audit once

After every segment is complete, audit the whole of `story.md`, not each segment in isolation. Read [references/quality-review.md](references/quality-review.md) and check:

- the first 300–500 characters create pressure, anomaly, conflict, or a decision;
- the protagonist has a visible goal and makes consequential choices;
- scenes create new information, resistance, decisions, gains, losses, or relationship change;
- setup and payoff are traceable;
- characters act from established goals and knowledge;
- mobile-reading paragraphs are readable without choppy sentence fragments;
- the ending fulfills the chosen direction and `endingPromise`.

Save a single audit result:

```text
python <skill-dir>/scripts/story_state.py audit <project-dir> --input <audit.json>
```

Decision meanings:

- `accepted`: ready to deliver.
- `patchable`: local fixes can make it deliverable.
- `replan_required`: the core structure or user intent is broken.

Do not invent critical issues to trigger unnecessary rewriting. Ordinary local prose, pacing, or payoff weaknesses are `patchable`.

### 6. Repair at most once

If the audit is `patchable`, repair only affected segments once. Preserve all unmentioned facts, events, tone, and ending promises. Do not replace human-edited segments; record those as residual debt instead.

```text
python <skill-dir>/scripts/story_state.py repair <project-dir> --input <repair.json>
```

After applying the repair, inspect the changed segments against every critical audit issue. If a critical issue remains, stop and report the blocker; do not silently mark the work complete.

### 7. Remove AI-flavored prose before finalize

After the whole-story audit and the one permitted repair, run `$story-deslop` on the complete `story.md` before delivery. This is the final S1A quality pass and must finish before S1B creates its source snapshot.

- Resolve the sibling `story-deslop` skill directory and follow its three-layer method.
- Diagnose the complete story, but apply approved prose changes to affected `segments/NN.md` through `edit-segment`; never leave edits only in a directly modified `story.md`.
- Allow expression, paragraph focus, and restoration of already-established causality. Do not add events, motives, evidence, dialogue, or new story facts in this pass.
- Resolve blocking findings from `check-ai-patterns.js` and `check-degeneration.js`, or register only explicitly justified writer-approved literal spans in the project's `.deslop-whitelist`.
- Run punctuation normalization as a check by default. Apply it only when the user or project explicitly asks.
- If the story still has a plot-level gap, return it to the audit/repair or replanning path rather than hiding it with prose.

After the de-slop pass, rebuild `story.md` from segments and run:

```text
python <ai-novel-short-story-dir>/scripts/story_state.py validate <project-dir>
```

The user may explicitly skip this pass for a faithful human-authored source; record the skip reason and residual style risk. AI-written stories do not skip it by default.

Show the de-slop result directly in the conversation: what changed by layer, a few representative before/after passages, remaining blocking or design gaps, and the backup location. Do not respond with only the report path.

### 8. Present for user approval, then finalize

Before calling `finalize`, deliver the full text from `story.md` directly in the conversation as continuous prose. Keep `review.md` and residual quality debt available, but do not include internal review notes in the story. Also state the file path and actual character count.

Then set the managed flow's G1-A gate to `等待用户确认` and end the turn. Do not call `finalize`, update the current production stage, or start storyboarding until the user explicitly confirms this story version.

After user approval, record the approved version in the flow state and run:

```text
python <skill-dir>/scripts/story_state.py finalize <project-dir>
```

A path-only response, progress update, or the agent's own reread is not user approval.

For later natural-language revision:

1. Identify the requested change and affected segments.
2. State whether it changes local prose, downstream causality, ending, scale, or core intent.
3. Ask for confirmation before changing completed prose that affects ending, scale, or core intent.
4. Apply only the confirmed scope; update the plan and downstream segments when causality changes.
5. Do not automatically invoke another full audit or another repair round.

After a revision, paste the affected revised prose directly in the conversation, not only the updated file path. If the revision changes the complete story flow, paste the revised full story or the complete affected sequence with enough surrounding context for the user to judge continuity.

If the user later wants a short-drama storyboard, offer `$short-story-to-drama-storyboard` as an optional downstream step. A single-episode short video uses 1 episode and 20–300 seconds; a series uses 2–40 episodes. Do not perform adaptation, scripts, or storyboarding inside this skill.

## Writing Standard

- Read the local `story.md` and `plan.md` in preference to reconstructing facts from conversation.
- Use concrete actions, choices, consequences, and natural dialogue.
- Keep mobile-oriented paragraphs mostly 1–4 sentences; do not split every sentence into a separate paragraph.
- Avoid plot summaries, abstract philosophy, repeated emotion labels, stacked metaphors, authorial conclusions, and crisis-time revelations.
- Genre payoff may be a breakthrough, counterattack, reveal, identity change, relationship fulfillment, or emotional release. Do not automatically turn every story into a face-slapping fantasy.
- Preserve the user's original idea. Deepen it without replacing its core resource, relationship, dilemma, or promised experience.

## Recovery

Run:

```text
python <skill-dir>/scripts/story_state.py status <project-dir>
python <skill-dir>/scripts/story_state.py validate <project-dir>
```

Resume from the first incomplete segment. Reuse completed segments. Never regenerate the entire story merely because the conversation changed.
