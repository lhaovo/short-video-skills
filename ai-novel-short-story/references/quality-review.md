# Quality Review

Read this after all segments are drafted and before applying a repair.

## Whole-story audit

Audit the complete continuous text once against the original idea, selected direction, causal contract, and ending promise.

### Critical failures

Use `severity: "critical"` only for:

- contradictory identity, quantity, truth, timeline, or ownership of a key object or fact;
- an unplanted new rule, ability, evidence, helper, or object resolving the climax;
- a character reversing position without a traceable motive;
- a key outcome that cannot be causally traced to earlier action;
- a story that is clearly below the user's target and cannot be considered complete;
- an ending that leaves the main question unresolved or contradicts the ending promise.

Critical failures cannot be downgraded to ordinary quality debt.

### Standard issues

Standard issues include:

- slow exposition or a late opening pressure;
- summary replacing dramatized events;
- long stretches without new information, resistance, or decision;
- unclear immediate goals;
- weak or repetitive payoff;
- excessive inner monologue or abstract commentary;
- paragraphs too dense for mobile reading;
- every sentence split into a fragment;
- unnatural dialogue;
- a competent or prominent setup that does not matter later.

Literary prose is not a defect. Diagnose only the concrete effect on readability, causality, and the promised experience.

## Decisions

```json
{
  "decision": "patchable",
  "summary": "The causal chain is complete, but segments 2 and 3 contain repeated explanation and a weak response to the board's decision.",
  "issues": [
    {
      "code": "repeated_explanation",
      "severity": "standard",
      "description": "The forged page is explained three times without a new consequence.",
      "affected_segment_orders": [2, 3],
      "repair_instruction": "Keep the evidence discovery once, then show the board's immediate reaction through action and dialogue."
    }
  ]
}
```

Choose:

- `accepted` only when no critical issue remains and the non-whitespace count is at least 70% of the target.
- `patchable` when replacing one or more complete segments can fix the story without changing the plan's core contract.
- `replan_required` only when the plan, ending, story scale, or core user intent must change.

## One-pass repair

The repair input replaces only affected complete segments:

```json
{
  "patches": [
    {
      "order": 2,
      "content": "Complete replacement prose for segment 2...",
      "continuity_summary": "Updated continuity after the repair."
    }
  ],
  "residual_quality_debt": [
    "The supporting character's office backstory remains lightly developed but does not affect causality."
  ]
}
```

Rules:

- Repair at most once.
- Do not alter segments outside the audit's affected scope.
- Do not overwrite a segment marked `humanEdited`.
- Preserve every unmentioned fact, event, tone choice, and ending promise.
- Fix the cause rather than hiding a contradiction with another new rule.
- After repair, verify that all critical issues are resolved. Ordinary residual debt may remain visible.

## S1A de-slop gate

After the whole-story audit and any permitted repair, run the sibling `story-deslop` skill before `finalize`.

- Scan the complete continuous story for expression, paragraph focus, and any remaining causality presentation problems.
- Apply approved prose edits to the affected segment files through `edit-segment`; do not leave them only in a directly edited `story.md`.
- The pass may not add events, motives, evidence, dialogue, or story facts. Plot-level gaps return to the audit/repair or replanning flow.
- Resolve blocking findings from `check-ai-patterns.js` and `check-degeneration.js`; advisory findings are judged in context.
- Punctuation normalization is check-only by default. Apply it only with explicit user or project authorization.
- Rebuild `story.md` and run `story_state.py validate` after the pass.

An explicitly skipped de-slop pass on a human-authored source is allowed only when the user wants faithful preservation. Record that choice and the residual style risk.

## User-facing report

Keep the delivery concise:

1. story title, target length, actual length, and ending received;
2. any residual quality debt in plain language;
3. the output path.

Do not paste audit JSON or internal segment identifiers into the final story.
