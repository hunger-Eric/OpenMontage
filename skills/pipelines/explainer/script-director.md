# Script Director — Explainer Pipeline

## When to Use

You are the Script Writer for a generated explainer video. You have a `brief` artifact from the Idea Explorer. Your job is to write a narration script from scratch — there is no existing footage to transcribe.

The script is the backbone of the video. Every visual, every scene, every audio cue flows from what you write here. A mediocre script cannot be saved by great visuals.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `proposal_packet` | Selected concept with title, hook, key_points, core_message, tone, narrative_structure, duration |
| Prior artifact | `research_brief` (optional but high-value) | Data points, audience insights, expert quotes — ground the script in real facts |
| Playbook | Active style playbook from `proposal_packet.selected_concept.suggested_playbook` | Voice style, pacing rules |
| Meta skill | `skills/meta/voice-performance-director.md` | Structured TTS delivery cues for natural, expressive narration |
| Layer 3 | TTS provider skills (check `agent_skills` on the selected TTS tool) | TTS capabilities for speaker directions |

## Process

### Step 1: Absorb the Proposal and Research

Read the `proposal_packet.selected_concept` carefully. Extract:
- **Target duration** — this is your word budget (see timing table below)
- **Hook** — your opening must deliver on this promise
- **Key points** — these must all be covered in the script
- **Core message** — the one thing the viewer should remember
- **Tone** — shapes word choice, sentence length, formality
- **Target audience** — shapes complexity and assumed knowledge
- **Narrative structure** — the structural approach (myth_busting, journey, data_narrative, etc.)

For reference-driven work, also read
`skills/meta/reference-production-handoff.md` and the proposal's
`metadata.reference_adaptation`. Start from its communication beats and approved
changes, not only the selected concept's short summary. Carry its reference in
the script metadata. Missing brand facts are a writing constraint: preserve the
story's function with supported, concrete content instead of repeating generic
advice to fill the target duration.

Then read the `research_brief` for grounding material:
- **`data_points`** — specific statistics and facts to weave into the script. Use claims with `surprise_factor: "surprising"` or `"counterintuitive"` as retention anchors.
- **`audience_insights.misconceptions`** — if the narrative structure is `myth_busting`, these are your myth/reality pairs.
- **`audience_insights.common_questions`** — address these directly in the script where they naturally fit.
- **`expert_voices`** — quotable experts add authority. Use sparingly — one or two per script.
- **`trending.recent_developments`** — if timely, reference them to make the content feel current.

**The research_brief is your cheat sheet.** Every fact, every surprising stat, every misconception is pre-verified and sourced. Use them. A script that cites "73% of developers..." (from research) is more compelling than one that says "many developers..."

### Step 2: Deepen Research Where Needed

The Research Director has already done the heavy lifting — you have a `research_brief` full of sourced facts. Your job here is targeted:

1. **Verify and update**: If any data point from the research_brief feels stale or uncertain, re-search to confirm.
2. **Fill script-specific gaps**: The research gives you broad facts. You may need a specific analogy, a precise technical detail, or a better example for a particular section.
3. **Find the best explanation**: How do the best educators (3Blue1Brown, Kurzgesagt, Fireship, Veritasium) explain this concept? What analogies work?
4. **Source quotable moments**: If the research_brief's expert_voices section has useful quotes, use them. If not, search for one strong quote to anchor a key section.

**Do NOT duplicate the Research Director's work.** If the research_brief already has 6 data points, you don't need to find 6 more. Focus on script-level needs: the right word, the right analogy, the right sequence.

### Step 3: Plan the Narrative Arc

Before writing prose, plan the structure. The following arc is useful for an
explainer; adapt it to the approved reference's communication purpose rather than
forcing a presenter demonstration or advertisement into an educational climax:

```
HOOK (0-5s)     → Grab attention. Question, bold claim, or surprising fact.
                   NEVER: "In this video, we'll learn about..."
                   NEVER: "Hey guys, welcome back..."

SETUP (5-15s)   → Why should the viewer care? Create a knowledge gap.
                   Show the problem or the question. Make them NEED the answer.

BUILD (15-Xs)   → Progressive revelation. Each section builds on the last.
                   Use "therefore / but" transitions, NOT "and then."
                   South Park rule: "This happened, THEREFORE that happened,
                   BUT then this complication arose..."

CLIMAX (X-5s before end) → The "aha" moment. Everything clicks into place.
                            This is the payoff for the setup's knowledge gap.

LANDING (last 5s) → Quick recap of core message + CTA.
                     Don't introduce new information here.
```

Map each of the brief's `key_points` to a specific section in the BUILD phase.

### Step 4: Write the Script

Before writing sections, create a top-level `voice_performance` plan using
`skills/meta/voice-performance-director.md`. The plan must describe the vocal
intent, pacing profile, energy curve, pause policy, and which passage should be
used in the existing speech sample. Do not leave this as a vague "natural voice" note.

For native dialogue, use the same performance intent in the video prompts rather
than planning a separate TTS track. Draft the complete spoken text first, with a
clear progression and ending; then divide it into semantic sections. Avoid giving
every section its own opening question, repeated instruction and closing slogan.
Attach delivery directions to the specific idea: emphasis, gaze, purposeful
gesture and the state in which the next passage continues. Section timings are
estimates, not fixed provider clip slots.

Write each section with these fields:

```json
{
  "id": "s1",
  "label": "Hook",
  "text": "Your database searches every single row. Every. Single. One. What if it didn't have to?",
  "start_seconds": 0,
  "end_seconds": 5,
  "speaker_directions": "Emphasize 'every single row' with measured pacing. Brief pause before the question.",
  "delivery_cues": {
    "pace": "measured",
    "energy": "curious",
    "emphasis_words": ["every", "single"],
    "pause_after_seconds": 0.6,
    "delivery_note": "Let the repetition feel intentional, then soften into the question.",
    "provider_text": "Your database searches every single row. Every. Single. One. <break time=\"0.6s\"/> What if it didn't have to?"
  },
  "enhancement_cues": [
    {
      "type": "animation",
      "description": "Database table with rows highlighted one by one, slowing down as count increases",
      "timestamp_seconds": 1
    }
  ],
  "pronunciation_guides": []
}
```

#### Timing Estimation

| Pace | Words/minute | Use when |
|------|-------------|----------|
| Conversational | ~150 wpm | Default for most explainers |
| Contemplative | ~120 wpm | Complex topics, need processing time |
| Energetic | ~180 wpm | Short-form, high-energy, TikTok/Reels |
| Technical | ~130 wpm | Code walkthroughs, architecture deep-dives |

**Word budget by duration:**
- 30s video → ~65-75 words
- 60s video → ~130-150 words
- 90s video → ~195-225 words
- 120s video → ~260-300 words

Count your words. If you're 20%+ over budget, the TTS will either rush or exceed duration. Cut ruthlessly.

The table estimates English speech. For Mandarin and other languages without
space-delimited words, estimate from spoken syllables/characters and the chosen
delivery, including purposeful pauses; do not use whitespace word counts. Refine
timing from the existing sample's actual delivery. If pronunciation needs repair,
keep the passage's meaning and its connection to the whole script while choosing
clearer wording.

#### Speaker Directions

For external narration, write directions that TTS can actually implement. Prefer structured
`delivery_cues` over prose-only `speaker_directions`:

| Direction | TTS Implementation |
|-----------|-------------------|
| "Speak slowly, with emphasis" | Lower speed setting, stability boost |
| "Excited, picking up pace" | Higher speed, higher style setting |
| "Pause for 1 second" | SSML `<break time="1s"/>` |
| "Whisper" | SSML whisper tag (model-dependent) |
| "Emphasize THIS word" | Note for post-processing or SSML emphasis |

Keep visual actions such as gaze and gestures in the scene/video direction,
separate from TTS instructions. For native dialogue, combine vocal delivery with
those actions in the corresponding video prompt.

**Expressive narration rule:** every narration-led section must include at
least two concrete cues among `pace`, `energy`, `emphasis_words`,
`pause_before_seconds`, `pause_after_seconds`, `delivery_note`, or
`provider_text`. Use `provider_text` when punctuation or SSML break tags are
needed to make the read sound human.

#### Enhancement Cues

Every section should have at least one enhancement cue. These tell the Scene Planner and Asset Generator what visuals to create.

| Cue Type | When to Use | Example |
|----------|-------------|---------|
| `overlay` | Key term, definition, label | "Show 'embedding' definition overlay" |
| `diagram` | Process, architecture, flow | "Mermaid flowchart: query → encode → search → rank" |
| `stat_card` | Surprising number or comparison | "Display: 1ms vs 500ms search time" |
| `animation` | Concept that needs motion to understand | "Animate vectors moving through high-dimensional space" |
| `code_snippet` | Code example | "Show Python: `results = collection.query(embedding)`" |
| `broll` | Real-world context | "Show examples of apps using vector search" |

**Density rule**: At least one enhancement cue every 8-10 seconds. A 60-second video should have 6-8 cues minimum. Viewers disengage if the visual doesn't change.

#### Pronunciation Guides

For technical terms, acronyms, and non-English words:

```json
{"word": "FAISS", "phonetic": "FACE"},
{"word": "Qdrant", "phonetic": "kuh-DRANT"},
{"word": "cosine", "phonetic": "CO-sign"}
```

### Step 5: Self-Evaluate — One Combined Review

After the complete draft, perform one combined review and reuse it for the stage
checkpoint. The script writer and EP are the same owner for ordinary short work;
do not run another scoring review or delegate the unchanged script for approval.

Check only:
- Content: follows the user's direction and selected proposal; coherent spoken
  progression, no obvious repetition, and factual claims traceable to the research.
- Timing: estimate once for the actual language and performance, including pauses.
  Treat word/character counts as a rough warning, not a mandatory universal 150 WPM
  formula. Do not pad useful short wording or repeatedly trim it solely to match a
  count; real generated speech timing is checked later against actual audio.
- Handoff: required schema fields, section times and references are present and
  consistent, with usable visual and delivery cues. Use the existing playbook
  guidance already read rather than rereading it for a separate checklist.

Validate the schema once when persisting the stage. The checkpoint writer's
validation is sufficient; do not add duplicate standalone validation commands.
After a concrete failure or content change, recheck only the affected points and
let persistence validate the changed artifact. Existing source/version identity
requirements remain, but unchanged hashes and references are not rechecked in a
loop. Record a brief review outcome; no eight-dimension scores, separate review
report or speculative polishing cycle is required. Repair actual defects only.

### Step 7: Submit

Validate `script_json` against the canonical script schema, persist it through
the checkpoint protocol, and attach the stage review. There is no separate
explainer submit function.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
Reuse its verified sources; do not repeat completed research as a script checklist.
Only a new or unresolved claim requires additional verification.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- **Clearly infeasible speech length**: Estimate for the chosen language and delivery once; shorten actual excess without repeatedly enforcing a generic word quota. Confirm exact timing against generated audio later.
- **Front-loading information**: The hook should create curiosity, not dump information. "HTTPS uses TLS 1.3 with AEAD ciphers" is a terrible opening. "The padlock icon doesn't mean what you think it means" is compelling.
- **Missing enhancement cues**: A script without visual direction is a podcast script. Every section needs at least one cue telling the visual team what to show.
- **Generic speaker directions**: "Read naturally" is useless. "Start measured and precise, then accelerate through the list to convey scale" is actionable.
- **Forgetting the audience**: A script for CTOs should use different words than one for high schoolers, even if covering the same concept.
- **No transitions between sections**: Each section should have a logical bridge to the next. The viewer should never think "wait, why are we talking about this now?"

## Example: Well-Written Section

```json
{
  "id": "s3",
  "label": "The Core Idea",
  "text": "Instead of matching keywords, vector databases convert everything — text, images, audio — into lists of numbers called embeddings. Similar things get similar numbers. So finding related content becomes a math problem: which numbers are closest?",
  "start_seconds": 15,
  "end_seconds": 28,
  "speaker_directions": "Measured pace through 'text, images, audio' with slight pause between each. Speed up slightly on 'similar things get similar numbers' — it should feel like a revelation. Brief pause before the final question.",
  "enhancement_cues": [
    {
      "type": "animation",
      "description": "Show text/image/audio icons transforming into number arrays (embeddings). Arrays cluster by similarity in a 2D space.",
      "timestamp_seconds": 16
    },
    {
      "type": "stat_card",
      "description": "Display: 'Everything becomes numbers. Similar things → similar numbers.'",
      "timestamp_seconds": 22
    }
  ],
  "pronunciation_guides": [
    {"word": "embeddings", "phonetic": "em-BED-ings"}
  ]
}
```

---

## Stage review

Reuse the combined review above and write the stage checkpoint using the current
manifest. Complete-plan human confirmation belongs to scene_plan; this stage
does not request a second human approval. Preserve an explicitly locked legacy
run policy and any new user-requested gate.
