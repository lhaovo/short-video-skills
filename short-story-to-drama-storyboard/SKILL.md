---
name: short-story-to-drama-storyboard
description: "Convert an existing Chinese short story into a single-episode short video (1 episode, 20–300 seconds) or a multi-episode short drama, including adaptation, episode scripts, quality-gated scene breakdown, and production-ready shot-by-shot storyboards. Use when the user wants a short story turned into short-drama storyboards; it does not write the original story, generate final images, or render video."
metadata:
  source: "Adapted workflow from https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant"
---

# Short Story to Drama Storyboard

Turn an existing short story into a vertical short-drama storyboard through a stable source snapshot, adaptation contract, episode scripts, quality review, and shot generation.

## Scope

- Start from an existing short story, normally the `story.md` produced by `$ai-novel-short-story`.
- Produce a vertical short-drama adaptation, episode outlines, performable scripts, and textual shot lists.
- **单集短视频：1 集，20–300 秒**
- 系列短剧：2–40 集，每集 20–300 秒。
- Do not rewrite or replace the source short story.
- Do not generate final character images, keyframes, video, subtitle files, or finished footage unless the user asks for a separate downstream production step.

## Persistent Drama Project

Resolve the directory containing this `SKILL.md` and use its `scripts/drama_state.py`.

If the source is `<story-project>/story.md`, use `<story-project>/drama/` as the default output directory. If the user names another output directory, use it.

### Mandatory sequence gate

When this production is managed by `short-video-flow`, S1B may start only after S1A has passed `G1-A`. Do not accept an existing storyboard, an existing story, or a user request to "go straight to prompts" as a reason to skip S1A or this stage.

Before initializing or modifying the drama project, run:

```text
python <short-video-flow-dir>/scripts/check_sequence.py --dir <production-dir> --enter S1B
```

The production directory is the parent of `01-故事/`. Exit code `0` is required. After exit code `2`, stop and return to the first incomplete stage in S1A.

An existing storyboard may be supplied only as reference material. It must still pass this stage's adaptation contract, episode scripts, quality gate, and current storyboard review. It cannot jump directly to S2.

The helper maintains:

```text
state.json                 authoritative adaptation and production state
source.story.md            immutable snapshot of the accepted source
adaptation.md              adaptation contract
episodes.json              structured episode outline
episodes.md                readable episode outline
scripts/01.md ...          per-episode performable scripts
quality/01.json ...        per-episode quality results
storyboards/01.json ...    structured shot lists
storyboards/01.md ...      readable episode storyboards
storyboard.md              final combined storyboard
```

Initialize only once:

```text
python <skill-dir>/scripts/drama_state.py init <drama-dir> --source <story.md> --episodes <N> --episode-seconds <N>
```

If the output directory already has a `state.json`, resume it instead of reinitializing. Run:

```text
python <skill-dir>/scripts/drama_state.py status <drama-dir>
python <skill-dir>/scripts/drama_state.py check-source <drama-dir>
```

If the source changed, stop and create a new drama project or explicitly replan existing work. Never silently pair an old storyboard with a new story version.

## Workflow

### 1. Diagnose the source

Read the full source snapshot, not only its synopsis. Determine:

- the protagonist's goal and central conflict;
- the irreversible facts and ending;
- the visual set pieces that should survive adaptation;
- material that can be compressed, combined, or reordered;
- the number and duration of episodes that fit the material.

Choose an episode count and per-episode duration from the actual story. Do not assume every short story should become the same fixed series length.

If no episode count is supplied, use the `ai-novel-short-story` project's `plan.md` only as supporting context; the source snapshot remains authoritative.

For adaptation criteria, read [references/workflow.md](references/workflow.md#1-source-and-adaptation).

Show the diagnosis directly in the conversation: proposed episode count and duration, what will be preserved, what may be compressed or reordered, and any declared deviation. The saved project remains the formal record, but a path-only response does not count as review.

### 2. Save the adaptation contract

Create a structured contract containing:

- title, genre, audience, logline, and vertical-drama positioning;
- the main pleasure or emotional through-line;
- at least three source facts that must survive;
- explicit allowed changes and declared deviations;
- core characters with a reusable visual anchor;
- optional paywall plan when the intended product uses paid episodes.

Use `visual_anchor` for stable casting and shot continuity. It should specify age range, appearance, clothing silhouette, and one distinctive detail without inventing an unrelated visual identity.

Save:

```text
python <skill-dir>/scripts/drama_state.py save-adaptation <drama-dir> --input <adaptation.json>
```

The exact JSON shape is in [references/contracts.md](references/contracts.md#adaptation).

After saving, paste the adaptation contract's key decisions into the conversation: positioning, emotional through-line, must-keep facts, allowed changes, declared deviations, and every core character's `visual_anchor`.

### 3. Build the episode outline

Create the full requested episode range or a clearly numbered production batch. Each episode needs:

- title;
- opening conflict, anomaly, or reversal in the first three seconds;
- hook type;
- core conflict;
- cliffhanger;
- emotional net change;
- source-beat references;
- target duration.

Every episode should change information, power, relationship, resources, risk, or the protagonist's choice. Do not split one static argument across several episodes merely to reach the episode count.

Save:

```text
python <skill-dir>/scripts/drama_state.py save-episodes <drama-dir> --input <episodes.json>
```

Use [references/workflow.md](references/workflow.md#3-episode-outline).

Show the complete episode outline for the requested scope directly in the conversation. For a large series, present it in clearly numbered production batches; never send only the `episodes.md` path.

### 4. Write episode scripts in order

Write one performable episode at a time. Each script must contain:

- visible action and character names;
- compact, speakable dialogue;
- a strong first-three-second hook;
- short scenes that continually escalate;
- an ending cliffhanger or decisive turn;
- a duration, scene count, and summary;
- any new hard facts introduced by the script.

Save:

```text
python <skill-dir>/scripts/drama_state.py save-script <drama-dir> --episode 1 --input <script.json>
```

Scripts are sequential. The next episode cannot be saved until the previous one exists. This protects continuity.

After saving each episode script, show that complete episode script in the conversation before moving to its quality review or storyboard. The user must be able to review action and dialogue without opening `scripts/NN.md`.

### 5. Review each episode

Score the script for hook, information density, paywall pull when applicable, emotion, duration, and consistency. Review platform-risk issues such as excessive violence, medical misinformation, superstition presented as fact, sexualized minors, dangerous instruction, or prohibited advertising language.

Save:

```text
python <skill-dir>/scripts/drama_state.py save-quality <drama-dir> --episode 1 --input <quality.json>
```

Quality decisions:

- `approved`: ready for storyboard.
- `continue_with_warning`: usable with visible residual risk.
- `repairable`: revise the script before storyboarding.
- `blocked`: do not storyboard.

Read [references/storyboard-quality.md](references/storyboard-quality.md#script-quality-gate) when reviewing.

Report the quality decision, score summary, concrete issues, and repair direction directly in the conversation. If the user only needs the final result, these checks may be summarized, but the complete script still has to be visible.

If `repairable` or `blocked`, rewrite the full episode script from a concrete repair instruction. The helper permits at most one automated repair per episode:

```text
python <skill-dir>/scripts/drama_state.py repair-script <drama-dir> --episode 1 --input <repaired-script.json>
```

After repair, run the quality review again. Do not generate a storyboard from a stale failed review.

### 6. Build one episode storyboard

Storyboard only an episode whose latest quality result is `approved` or `continue_with_warning`.

Create a shot sequence of 1–40 shots. Each shot must contain:

- order;
- shot size;
- camera movement;
- duration;
- location;
- visible action;
- dialogue when present;
- referenced character names;
- a visual prompt.

Each shot must advance conflict, reaction, reveal, decision, or consequence. Prefer close-ups and medium close-ups for vertical drama. Do not fill the sequence with decorative empty shots.

Save:

```text
python <skill-dir>/scripts/drama_state.py save-storyboard <drama-dir> --episode 1 --input <storyboard.json>
```

Use [references/storyboard-quality.md](references/storyboard-quality.md#storyboard-rules) and the JSON contract in [references/contracts.md](references/contracts.md#storyboard).

Show the complete readable storyboard for the episode being confirmed directly in the conversation, including shot number, duration, location, action, dialogue, and visual description. The JSON and `storyboard.md` are production records, not a substitute for user-facing delivery.

### 7. Finalize

Complete every episode's script, current quality result, and storyboard:

```text
python <skill-dir>/scripts/drama_state.py finalize <drama-dir>
```

The final user-facing delivery is both the complete content of `storyboard.md` shown in the conversation and its saved file. Keep `scripts/`, `quality/`, and episode JSON files available as production records. Do not reply with only the final path.

After presenting the current episode script and complete storyboard, set G1-B to `等待用户确认` and end the turn. Do not mark G1-B approved, return control for S2, or generate prompts until the user explicitly confirms this version.

After the user approves, record the approved version in the flow state, return control to `short-video-flow`, and do not begin S2 from this skill.

## Source Changes and Revisions

The accepted source is copied to `source.story.md`; all downstream work reads that snapshot.

If the original story changes:

1. Run `check-source`.
2. Report exactly what downstream assets become stale.
3. Preserve existing work.
4. Ask whether to create a new drama version or replan from the changed source.
5. Never automatically overwrite completed scripts or storyboards.

For a local storyboard change, preserve the underlying script and facts. For an episode-structure or source-fact change, update the affected script, rerun quality review, then regenerate the affected storyboard.

## Recovery

Run `status` and `validate`, then resume from the first missing or stale stage. Reuse completed artifacts when their source hash still matches.
