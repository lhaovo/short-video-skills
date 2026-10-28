# Workflow Details

Read only the section needed by the current stage.

## 1. Interpret and route

Choose short form based on the amount of change the premise can sustain:

- Short form fits when one protagonist can pursue a concrete goal through a compact causal chain and the core question can be paid off within 30,000 characters.
- Route away from this skill when the idea requires several major worlds, a long progression system, a large cast with multiple independent arcs, or an ending that cannot be reached without long-form accumulation.
- Do not classify by keyword or genre name alone.

When no target is supplied, choose a realistic target between 3,000 and 30,000. Consider the number of causal turns, scene count, and ending cost. State the chosen target and why it fits.

Useful platform tendencies:

| Profile | Useful default |
| --- | --- |
| 知乎短故事 | Fast entry, first-person intimacy, strong narrative question |
| 番茄短篇 | Direct prose, frequent state change, strong chapter-level pull |
| 通用中文商业网文 | Concrete scene progression, active protagonist, clear payoff |

Platform tendencies do not override the user's explicit style, topic, or constraints.

## 2. Directions

Create exactly three viable directions. No pair may differ only by names or titles. Across the three options, vary the major dimensions:

- what emotional experience the reader gets;
- how the central conflict escalates;
- what kind of ending payoff resolves the story.

Input JSON:

```json
{
  "understanding": "The user wants a restrained revenge story about a woman reclaiming control of her family business.",
  "recommendation_reason": "The conflict can be resolved in one compact causal chain, so short form fits.",
  "platform": "知乎短故事",
  "platform_reason": "The intimate, high-pressure premise suits a compact first-person narrative.",
  "directions": [
    {
      "id": "ledger",
      "title": "她把账本留到了最后",
      "premise": "A woman returns to audit the family company she was forced out of and discovers her expulsion was engineered.",
      "core_experience": "Controlled pressure followed by a decisive public reversal.",
      "protagonist": "Lin Zhao, a disgraced former finance director who returns with her own evidence.",
      "central_conflict": "She must expose the fraud before the board approves a merger that erases the evidence.",
      "ending_promise": "The fraud is exposed through evidence she gathered herself, and she regains control without relying on an unplanted rescue.",
      "style_keywords": ["克制的压迫感", "证据链推进", "公开对峙"]
    },
    {
      "id": "heir",
      "title": "遗嘱里没有我的名字",
      "premise": "An overlooked daughter inherits only a key and must find the room it opens before her siblings sell the house.",
      "core_experience": "Family mystery resolving into emotional recognition.",
      "protagonist": "Su Wan, an overlooked daughter who believes she has no claim to the family legacy.",
      "central_conflict": "Her siblings obstruct her search while the house's buyer moves up the deadline.",
      "ending_promise": "The key reveals her father's deliberate protection and gives her a future she chooses for herself.",
      "style_keywords": ["家庭悬念", "物件线索", "克制亲情"]
    },
    {
      "id": "last-nine-minutes",
      "title": "开盘前九分钟",
      "premise": "A junior risk analyst discovers that the market crash in nine minutes was pre-recorded by the trading system.",
      "core_experience": "A real-time countdown where every attempt to expose the manipulation narrows her escape route.",
      "protagonist": "Chen Yu, a junior risk analyst who is scheduled to take the blame for a failed trading model.",
      "central_conflict": "She must preserve the tampered logs while the trading floor treats every alarm as a test.",
      "ending_promise": "She proves the crash was deliberate and forces the system owner to acknowledge the fraud.",
      "style_keywords": ["实时倒计时", "技术证据", "密闭空间"]
    }
  ]
}
```

Do not use abstract literary labels as the whole style profile. Make style keywords executable for pacing, conflict, and viewpoint.

## 3. Plan

The plan is a causal contract, not a list of word-count buckets.

### Plan rules

- Use 2–8 segments.
- Segment orders must be consecutive from 1.
- Segment targets must sum to within `max(500, 8% of total)` of the total target.
- Each segment must have 2–6 progressive beats.
- Every segment creates a visible state change and a reason to continue.
- The final segment answers the central question and fulfills the ending promise.
- At least two setup/payoff pairs must be recorded.
- At least one fixed fact should establish the protagonist's identity or competence.
- A critical solution may not be introduced for the first time during the climax.

### Planning method

1. Start from the ending promise.
2. Define the central causal question.
3. Identify the first pressure that forces action.
4. Alternate attempts and consequences until the final choice.
5. Plant each decisive object, rule, relationship, or clue before it matters.
6. Give each segment a new local goal and a different kind of payoff.
7. Remove any beat that does not change knowledge, power, relationship, resources, risk, or choice.

Input JSON:

```json
{
  "title": "她把账本留到了最后",
  "target_word_count": 8000,
  "ending_promise": "She exposes the engineered expulsion with evidence she gathered and chooses whether to reclaim control.",
  "segments": [
    {
      "order": 1,
      "purpose": "Force her back into the company under immediate threat.",
      "target_word_count": 1800,
      "opening_state": "She has been out of the company for three years and needs the audit fee.",
      "opening_hook": "The current finance director panics when she asks to see the original ledger.",
      "immediate_goal": "Get access to the archive before the merger vote.",
      "progression_beats": [
        "The security record proves the files were moved the night she was fired.",
        "She chooses a temporary ally inside the audit team.",
        "Her former assistant warns that the buyer already knows she is back."
      ],
      "turning_point": "The archived ledger contains a page in her own handwriting that she never wrote.",
      "payoff": "She realizes the accusation against her was built from forged evidence.",
      "closing_pull": "The forged page carries a timestamp from the one hour she can prove she was elsewhere.",
      "closing_state": "She has a concrete way to challenge the official narrative."
    },
    {
      "order": 2,
      "purpose": "Escalate the counterattack and force a final public choice.",
      "target_word_count": 2200,
      "opening_state": "She has an alibi and only hours before the vote.",
      "opening_hook": "The ally sends her a withdrawal record tied to her former assistant.",
      "immediate_goal": "Get the evidence into the board meeting without losing the original files.",
      "progression_beats": [
        "The buyer offers to restore her position if she suppresses the forgery.",
        "She refuses and accepts the risk of losing the audit contract.",
        "A power failure threatens the digital copy, so she carries the physical ledger."
      ],
      "turning_point": "Her former assistant admits the forgery but reveals the buyer ordered it.",
      "payoff": "The board sees the complete chain of custody and rejects the merger.",
      "closing_pull": "She is offered the chair but asks for the audit to continue first.",
      "closing_state": "She has cleared her name and chooses accountability over immediate status."
    },
    {
      "order": 3,
      "purpose": "Resolve the aftermath and personal consequence.",
      "target_word_count": 4000,
      "opening_state": "The merger is stopped, but the company is exposed and unstable.",
      "opening_hook": "Her former assistant refuses to leave until she promises no private retaliation.",
      "immediate_goal": "Decide whether to take power or publish the full investigation.",
      "progression_beats": [
        "Employees reveal further losses hidden by the former director.",
        "Publishing the report will harm innocent staff but prevent an immediate cover-up.",
        "She chooses a supervised restructuring and resigns the temporary chair role after one condition is met."
      ],
      "turning_point": "Her former assistant provides the missing list of accounts used for the fraud.",
      "payoff": "She receives a formal apology, keeps the evidence public, and completes the audit.",
      "closing_pull": "She leaves the office carrying her own notebook, not the company's.",
      "closing_state": "She has regained agency and a professional future without accepting a falsely clean victory."
    }
  ],
  "causal_contract": {
    "protagonist_goal": "Expose the fraud behind her expulsion before the merger erases the evidence.",
    "central_question": "Can she prove the accusation against her was engineered?",
    "fixed_facts": [
      "She was the original finance director before being forced out three years ago.",
      "The original ledger has a complete chain-of-custody log.",
      "The merger vote is the deadline for evidence destruction.",
      "The audit-team ally can access security records but not alter them."
    ],
    "cause_effect_chain": [
      "Because the merger would erase the archive, she must return immediately.",
      "Because she reclaims the original ledger, she can challenge the forged page.",
      "Because the ally supplies the withdrawal record, she can tie the forgery to the buyer.",
      "Because she refuses to suppress the evidence, the board must confront the full chain.",
      "Because she chooses public accountability, the ending resolves both the fraud and her personal exile."
    ],
    "setup_payoffs": [
      {
        "setup": "The missed timestamp in her old calendar gives her an alibi.",
        "setup_segment_order": 1,
        "payoff": "The forged page is dated during that proven absence.",
        "payoff_segment_order": 2
      },
      {
        "setup": "The original ledger's custody log is mentioned before the archive search.",
        "setup_segment_order": 1,
        "payoff": "The log survives the power failure and proves the forgery.",
        "payoff_segment_order": 2
      }
    ]
  }
}
```

The example is illustrative. Match style and structure to the actual user request.

## 4. Segment writing

For each segment, write from these inputs:

- original idea and user constraints;
- selected direction;
- full plan and causal contract;
- current segment contract;
- previous continuity summary;
- final paragraph of previous prose;
- platform and style guidance.

The first segment must reach pressure, anomaly, conflict, or a decision within the first 300–500 characters. Do not open with weather, waking up, a mirror, extended backstory, a dream, or world-building exposition.

Do not write segment titles into prose. Save a continuity summary separately for machine use. The summary should state:

- what changed;
- who knows what;
- current location and time;
- resources gained or lost;
- active promises and unresolved dangers;
- the exact moment where the segment stops.

## 5. Revision routing

Classify a requested revision before changing files:

| Scope | Strategy |
| --- | --- |
| Wording, local pacing, small dialogue fix | `local_patch` |
| A changed fact or choice that affects later consequences | `rewrite_downstream` |
| Ending, story scale, protagonist goal, or core experience changes | `full_replan` |

For `full_replan`, draft a new plan and show the affected ending, scale, and segments before applying it. Preserve the original version until the user confirms.
