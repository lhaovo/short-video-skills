# Workflow Details

Read only the section required by the current production stage.

## 1. Source and adaptation

The immutable source snapshot is authoritative. A readable `plan.md` may explain intent, but it cannot override facts in `source.story.md`.

### Choose the production shape

Choose episode count and duration from:

- the number of distinct causal turns;
- the number of major visual set pieces;
- the size and complexity of the cast;
- how many emotional reversals the central conflict can sustain;
- the intended paid or free release model.

Typical outcomes:

- single-episode short video: exactly 1 episode, 20–300 seconds;
- compact single incident: 6–12 episodes;
- multiple reversals and a mid-story reveal: 12–24 episodes;
- ensemble or layered conflict from a long short story: 20–40 episodes.

These are ranges, not quotas.

### Adaptation contract

Keep the source's:

- core protagonist goal;
- central dramatic question;
- emotional promise;
- ultimate ending;
- facts without which the ending fails.

Allowed changes should be explicit. Typical changes include:

- combining minor characters;
- moving exposition into conflict;
- making a verbal reveal visual;
- cutting subplots that do not affect the main question;
- reordering scenes when causality and knowledge state remain credible.

Declared deviations are changes that alter the source. Do not hide them.

### Character visual anchors

Use a visual anchor to keep casting and storyboard continuity stable:

```text
Age range; build; face/expression quality; hair; silhouette; clothing palette; one distinctive detail.
```

Avoid unrequested ethnicity, body, or costume changes. If the source does not determine appearance, choose the minimum detail needed for consistency.

## 2. Episode structure

Each episode should contain a local escalation and a change that forces the next episode.

A useful working rhythm is:

```text
hook → immediate response → complication → reversal or reveal → choice → new pressure
```

Do not mechanically place an identical beat pattern in every episode. Vary the source of pressure:

- evidence;
- misunderstanding;
- relationship shift;
- deadline;
- resource loss;
- public exposure;
- moral choice;
- consequence of an earlier lie.

### Three-second opening

The first three seconds should present conflict, anomaly, danger, a reversal, or a decision point. Avoid slow establishing scenery, narration that explains backstory, or a character waking up without immediate pressure.

### Cliffhanger

A cliffhanger should change the next choice or reveal a new cost. A question alone is weak if nothing in the scene changed.

Do not end an episode with a false crisis that the next episode immediately cancels without consequence.

## 3. Episode outline

Create one entry per episode with:

- consecutive `order`;
- `title`;
- `hook_opening`;
- `hook_type`;
- `conflict`;
- `cliffhanger`;
- `emotion_net` from -5 to 5;
- `source_beats`;
- `target_duration_sec`.

If the story uses paid episodes, mark intended paywall episodes and ensure the payoff after the paywall is stronger than the buildup before it.

### Source mapping

`source_beats` may be short labels rather than page numbers. They should let the editor locate the source material. Every major script episode should retain at least one traceable source fact, choice, or event.

## 4. Episode script

Use a compact script format that can be performed or storyboarded:

```text
场景 1｜地点｜时间

动作：...

角色名：对白。

动作：...
```

Keep novel-style internal monologue out of the performable body. Convert a key thought into:

- an action;
- a glance;
- a line of dialogue;
- a visible object;
- an interruption;
- a tactical choice.

The script should specify enough action for a director to understand staging while leaving shot selection to the storyboard stage.

## 5. Quality review

Score each area from 0 to 100:

- hook;
- information density;
- paywall pull;
- emotion;
- duration;
- consistency;
- overall.

Use `continue_with_warning` only for issues that do not prevent shooting. Use `repairable` for local structural, pacing, dialogue, or consistency fixes. Use `blocked` when the script is unusable, contradicts hard facts, or cannot be made safe without major replanning.

Every issue should point to evidence and a concrete fix. Avoid generic criticism such as “make it more dramatic.”

## 6. Storyboard

The storyboard converts a script into visible shots. It must preserve:

- character identity and visual anchor;
- location;
- time/weather continuity when material;
- action direction;
- dialogue source;
- causal order;
- episode hook and cliffhanger.

Useful shot-size vocabulary:

- `远景`
- `全景`
- `中景`
- `中近景`
- `近景`
- `特写`
- `大特写`

Camera movement should have a purpose:

- push in for realization or pressure;
- pull out for isolation or consequence;
- pan for discovery;
- handheld for urgency, used sparingly;
- static when performance carries the scene.

A dialogue line may be split across reaction shots when the reaction changes meaning. Do not create one shot per sentence mechanically.

## 7. Source revision routing

| Requested change | Required downstream action |
| --- | --- |
| Change one shot composition | Replace only that episode storyboard |
| Change dialogue within an existing scene | Update script, review, storyboard |
| Add or remove a scene | Update episode outline, script, quality, storyboard |
| Change episode order or episode count | Regenerate affected outline and all downstream episodes |
| Change a hard source fact or ending | Start a new adaptation version |
