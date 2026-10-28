# Storyboard and Script Quality

## Script quality gate

Review the complete episode script, not only its summary.

### Score guidance

| Dimension | High score means |
| --- | --- |
| Hook | The first three seconds create conflict, danger, anomaly, reversal, or a decision |
| Density | Information, resistance, power, resources, or emotion change continuously |
| Paywall | A paid stopping point would create strong continuation pressure without cheating |
| Emotion | The audience can identify and follow the intended emotional movement |
| Duration | Scene and dialogue volume fit the declared episode length |
| Consistency | Characters, facts, locations, props, and knowledge remain coherent |
| Overall | The episode is performable and serves the adaptation promise |

### Status rules

- `approved`: no high or critical issue remains.
- `continue_with_warning`: usable, but at least one medium issue remains visible.
- `repairable`: a bounded rewrite can fix the episode without changing the series plan.
- `blocked`: the episode is unusable or unsafe, contradicts a hard fact, or requires structural replanning.

### Common issues

- opening uses narration or scenery instead of immediate pressure;
- an episode restates what the audience already knows;
- one conversation spans the whole episode without a power shift;
- the cliffhanger asks a question without changing a fact or choice;
- a character reveals knowledge they did not acquire;
- a solution appears without setup;
- the script is novel prose rather than shootable action and dialogue;
- the episode exceeds the planned duration;
- the intended paywall episode lacks a sufficiently strong turn.

### Safety and platform review

Flag rather than normalize:

- excessive violence or gore;
- medical or legal misinformation;
- superstition presented as verified fact;
- sexualized minors;
- detailed instructions for dangerous or illegal behavior;
- prohibited absolute advertising claims;
- content that relies on a protected-minority stereotype.

Use `blocked` when the risk must be removed before any visual production.

## Storyboard rules

### Coverage

A shot list should cover:

- the opening hook;
- the protagonist's immediate reaction;
- the source of pressure;
- evidence or information reveals;
- the decisive action;
- the reversal;
- the final image or cliffhanger.

### Shot design

- Use a close-up or medium close-up when expression or evidence carries the moment.
- Use an establishing or full shot only when location changes the action or scale.
- Use camera movement for emphasis, not decoration.
- Preserve screen direction through conversations and chases.
- Match props, wardrobe, time of day, and location between shots.
- Keep dialogue attached to the speaking or reaction shot it affects.
- Use cuts or insert shots to make key evidence readable on a phone.

### Continuity

Before saving the storyboard, check:

- episode number and title;
- every character reference exists in the adaptation contract;
- locations match the script;
- props and evidence maintain identity;
- the final shot expresses the script's cliffhanger;
- shot order is consecutive;
- per-shot durations are plausible for the declared episode duration.

### Final output

`storyboard.md` should be readable by a director without opening the JSON:

```text
第1集《标题》

镜头 1｜中近景｜4秒｜婚礼宴会厅
运镜：手持跟拍
人物：苏遥、林夏
动作：...
对白：...
画面：...
```

Do not include adaptation research, quality scores, source hashes, or production diagnostics in the final storyboard unless the user asks for a technical appendix.
