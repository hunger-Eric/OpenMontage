# Reference Production Handoff

## Scope and ownership

Use for every reference-driven production, regardless of intake channel or
selected pipeline. Read alongside `video-reference-analyst.md` and the selected
stage director, not instead of either. Editing supplied footage alone does not
trigger this workflow. Existing user choices and manifest approval gates remain
authoritative; this skill adds no human approval gate or provider default.

The agent owns reference interpretation, adaptation, writing, performance
direction and creative acceptance. Tools own acquisition, probes, measurements,
schema validation, media transformations and persistence. A checkpoint or a
schema-valid artifact is not evidence that the creative work occurred.

## 1. Turn the reference into a story and edit map

Bind observations to the frozen local source path, SHA-256, duration and analysis
artifact. Separate observed, inferred and unverified claims.

Identify the reference's communication logic through the original method's
connected reading and timestamped evidence:

- Audience and purpose; hook, setup, progression, evidence/payoff and ending.
- What each narrative beat contributes, rather than just what appears onscreen.
- Spoken content versus on-screen copy; speaker role, delivery, pauses, emphasis,
  performance progression and music/environmental sound where actually verified.
- Why the edit changes shots: speech meaning, action, reveal, emphasis or contrast.

Unknown audio semantics remain unverified. Frames cannot establish voice quality
or lip sync; a transcript cannot establish performance. Model descriptions of
sound remain provisional without appropriate actual-media validation.

Work along the source timeline, relating what is said, what is shown and why the
shot changes. A detected shot is a visual boundary, not necessarily a new story
beat: one spoken thought can span several shots. Keep the original-language
transcript alongside its meaning when translating; write the adaptation in the
target language's spoken idiom rather than translating subtitles word for word.
Describe the presenter's role (guide, witness, demonstrator), how the delivery
develops and where inserts carry the explanation while speech continues.

The analysis method is the migrated Hypit reference reading linked by the analyst,
not a replacement shot checklist. Read its `ANALYSIS.md` and `TIMELINE.md` through
the brief's `reference_understanding.notes`; preserve unresolved questions in
`PROGRESS.md`. Reference their paths/hashes alongside the existing analysis/source
identity in `reference_evidence`. Take the observed action and camera behavior,
visual systems and their timed handoffs into the target scene and full prompt.
Do not reduce that connected reading to a broad summary and repeat one fixed
camera setup across all requests. The original Video direction explains when an
actual source excerpt should carry distinctive motion to a supported model.

## 2. Make the adaptation explicit before production

Resolve `mode` from the user's actual intent, not a keyword classifier in code.
“复刻”/“复制” alone is not a request for identical content or timing. A request to
borrow pacing, voice character, composition or explanation format uses
`creative_adaptation`: preserve those dimensions and adapt the message/product
to the user's goal. Keep the actual reference's production grammar; do not replace
it with a generic story or require a different visual style to demonstrate novelty.
Use `faithful_replica` only when the user explicitly asks to retain source
content/order/timing, plus authorized brand/original sound. Omitted mode remains
compatible with historical adaptation artifacts; do not rewrite them. An already
specified expression/content direction needs no extra mode-choice question.

In the existing `intent`, record what to keep and what to change, grounded in
timestamped evidence. As applicable, describe rhythm (speech density, pauses,
cut triggers, reveals), voice character/delivery (pitch range, texture, energy,
emphasis), composition (shot size, subject placement, foreground, camera), and
explanation format (presenter/voiceover/inserts, question-to-demonstration flow,
text/diagram support). These are creative requirements, not mandatory fixed
values or fields for every video. Carry them through script, scene prompts,
voice direction and actual-media review via the same proposal SHA.

For creative adaptation, source timecodes are evidence of relationships rather
than mandatory target cut positions. Derive final timing from the new speech,
actions and footage; preserve the intended pace and information progression.
Similar voice character does not itself authorize reusing the source soundtrack
or cloning a particular speaker. Resolve the intended voice using the existing
audio architecture and provider policy. Review against the selected dimensions,
not frame equality; the strict replica clock/compiler is not this mode's gate.

Choose the pipeline by the approved delivery grammar and ownership of footage,
not by the analysis tool's suggested pipeline, intake channel or available render
engine. Explain the fit in the proposal. A generated presenter ad need not be
treated as an educational explainer; a footage-led pipeline is not suitable just
because the reference contains a real presenter. Use the matching manifest and
its director skills once the choice is made.

Store one canonical adaptation plan at
`proposal_packet.metadata.reference_adaptation`. The existing free-form metadata
field accepts it; do not invent fields in strict `production_plan` objects.
Include:

- `reference_evidence`: source path/hash, analysis path/revision and boundaries.
- `intent`: viewer, purpose and approved changes from the reference.
- `pipeline_rationale`: why this pipeline fits the requested film.
- `beats`: IDs, source time ranges, communication function, what to keep/change,
  target adaptation and evidence status. Functions may be combined or reordered
  when the user-approved adaptation requires it; this is not a copying template.
- `continuity`: speech architecture and voice strategy, character identity,
  performance progression, visual/action continuity and audio transition plan.
- `review_scope`: the adjacent beats and transitions to inspect during full production.
- `unverified`: gaps, their impact and what evidence would resolve them.

Removing a reference's brand, prices or promises does not remove its narrative
function. Replace them with supported information, or disclose the resulting
change in purpose; do not fill the space with repetitive generic reminders.
This advice applies to approved adaptation changes. Faithful mode must not remove
or replace source claims/branding by default. Record actual source wording and
uncertainty without treating copied claims as independently verified facts.

### Bind references to the actual generated passage

Apply the migrated Hypit [reference relationships](../../third_party/hypit/references/playbooks/craft/generated-dependencies.md)
and [input responsibilities](../../third_party/hypit/references/playbooks/craft/video-direction.md#give-each-input-its-own-responsibility).
The agent selects references from the visible facts each shot needs. Do not
append a production-wide character card or scene pack to every generation.
For a ship/port-only passage, omit an unused presenter image and visible-speaker
instructions. An offscreen continuing voice does not make a portrait a voice
reference; follow the already selected speech architecture.

For each request, state in the existing required-asset description/full prompt:
the actual filename or request-local reference label, the fact it supplies,
the target shot/time range where it applies, and relevant facts to change or
exclude. Character appearance, setting, composition, motion, exact endpoints
and voice identity are separate responsibilities. Borrow only the required
facts; a warehouse portrait need not impose its warehouse or pose on a port.

A multi-shot request may use several references when their roles and ranges
are explicit. For example, in a ship -> yard -> presenter-at-laptop passage,
the ship/yard motion reference serves the aerial shots and the character image
serves only the final human shot. Do not request that person in every frame.
If the selected mode cannot reliably separate those influences, choose useful
generation boundaries and edit the results under the existing audio/timing
contract; do not silently change native speech, model or provider.

Select motion excerpts for the relevant action/camera passage; do not include
unrelated people or operations merely to fill the desired duration. Respect
the selected mode's real duration behavior, including source-video inheritance.
Do not declare an unsupported local influence mask or duration override.

Before submission, compare this shot's selected upload list, active composer
associations and full prompt. A file stored in the project's library is not
automatically an active reference. Remove irrelevant/stale associations through
the supported interface; a successful upload alone does not establish relevance.
Relevance and reference scope are agent judgments, not filename/keyword rules.
After generation, inspect actual subjects, setting, framing and cut handoffs
for reference contamination. Preserve accepted media and original requests;
document a revised mapping for future work rather than rewriting past receipts.

### Executable faithful timeline

Keep the payload at `proposal_packet.metadata.reference_adaptation.replica`,
validated by `schemas/artifacts/reference_replica.schema.json`. No second plan:

- `reference_evidence.source_path` and `sha256` identify the frozen source.
- `replica.fps`, `total_frames`, `width`, `height`, `background_color` define the measured, explicitly
  rounded final clock/geometry. Units cover it in order without gaps.
- Each `units[]` entry has `id`, `source_start_frame`, `source_end_frame` (exclusive),
  `action`, `composition`, `internal_cuts` (absolute source frames), and `material`
  (`generated_video` or `authorized_brand`). Describe foreground, subject position,
  camera/viewpoint, action progression and internal cut handoffs from actual media.
  The agent chooses unit boundaries; code does not infer them from fixed templates.
- `captions[]` records source-timed `id`, `unit_id`, `start_frame`, `end_frame`,
  `text` and explicit `style` fields defined by the schema. Record OCR/word-time/font
  uncertainty. The agent authors layout and motion; the renderer executes them.
- `audio` declares `policy` (`reuse_source`, `replace`, `none`), `authorized`, and
  for audible layers `path`, `sha256`, `provenance`. Original-audio reuse requires
  explicit copying authorization; changed language/copy follows the existing audio
  architecture. Neither identity images nor source-video conditioning proves lip sync.

After saving the canonical proposal, create its `{proposal_path, proposal_sha256}`
reference. Prepare each generated unit locally through the registered tool:

```python
registry.get("video_trimmer").execute({
    "operation": "reference_clip", "reference_adaptation_ref": proposal_ref,
    "reference_unit_id": unit_id, "output_path": new_source_clip_path,
})
```

The result contains the derivative hash/range/duration and `reference_receipt_path`.
Reuse that exact clip and receipt. Pass `reference_adaptation_ref`,
`reference_unit_id`, `reference_receipt_path` and the clip in `reference_paths` to
the selected `video_selector` request. For Flow use its already registered
`google_flow_mcp_video` adapter and configured MCP. No fixed provider/model is
selected by this contract. A route lacking source timeline binding reports its
gap; do not switch it silently. Identity images are optional: check their view
does not override source framing. Keep the complete motion prompt authored by
the agent, with source action/camera/internal-cut instructions. Source-video mode
inherits duration; ordinary UI request seconds are not effective output duration.
The adapter verifies active references and settings again before the paid click.

At edit, put `reference_adaptation_ref` in both edit and asset-manifest metadata.
`edit_decisions.metadata.reference_timeline` is a projection referencing that SHA:

- `segments[]`, in unit/cut order: `unit_id`, `cut_id`, `media_sha256`,
  `fidelity_review={status: pass|fail|unverified, observations: ...}`. Review actual
  composition/foreground/camera, action/internal cuts, rhythm, embedded text and
  promised lip sync. Keep unverified dimensions in observations and status.
- Each canonical cut selects an asset and its actual `in_seconds/out_seconds`.
  Match source duration; measured output must cover the range. An authored speed
  change needs `time_transform_reason`. Never stretch every clip to its slot.
  An explicit `end_hold_frames` plus that reason can hold the selected end frame
  for a short measured gap; code never adds this automatically.
- `caption_dispositions[]`: `cue_id`, `handling=overlay|embedded|omit`, `evidence`,
  and the selected unit's `media_sha256`.
  Every cue is accounted for exactly once. Embedded residue stays in review and
  suppresses duplicate overlays; it never becomes an editable caption. Omitting
  content is a disclosed deviation requiring the existing creative decision rules.
- Each segment review has separate `checks` for `composition`, `action`, `timing`,
  `embedded_text`, `lip_sync`, using `pass|fail|unverified|not_applicable`.
  A failed/unverified dimension cannot be declared an overall pass.
- Optional `fade_frames` executes an authored picture fade, including brand stills.

`video_compose(preflight)` consumes these bindings, checks source/media/audio
hashes, measured trim ranges, order, durations and caption dispositions.
`preview` routes the payload to the registered Remotion `ReferenceReplica`
composition: generated video muted, one authorized audio layer, explicit text
layers and brand material. It adds no padding, reframing, default story or model
selection. Geometry comes from the source contract. Do not combine this route
with atelier/profile overrides, duplicate subtitles or other overlay routes.
Keep existing final technical and semantic gates. Preview records reference
fidelity independently; `finalize` refuses faithful delivery while it is unresolved.
The owner visual review must also include `reference_fidelity` for this exact
preview: `status=pass`, frozen `source_sha256`, `proposal_sha256`, actual `evidence`,
and separate `checks` for `content`, `order`, `rhythm`, `composition`, `captions`,
`audio`, `lip_sync` (`pass|not_applicable`). Unknown audio/mouth timing cannot pass
this whole-film comparison just because per-segment media is valid.
Compare the actual continuous preview with the original, enlarge motion/cut
boundaries, and update only failed leaves. Whole-frame visual evidence cannot
pass audio or mouth timing. Preserve all original attempts, accepted siblings,
unknown jobs and exact-prompt UI recovery receipts without claiming API success.

For an unbranded demonstration, preserve the progression using concrete,
illustratable actions rather than inventing company claims. For example, a
warehouse story can move from "what is being shipped" to "how it is prepared"
to "how the handoff is documented". It should not repeat "count, pack, explain"
in every section. Choose one point of view and a clear ending for the whole film.

Downstream canonical artifacts use
`metadata.reference_adaptation_ref = {proposal_path, proposal_sha256}` to point
to the approved proposal revision. Do not copy mutable plans across artifacts.
An approved revision requires dependent references and reviews to be refreshed;
reuse unaffected, accepted media. Legacy runs are inspected and continued from
their real evidence, never bulk-rewritten or given fabricated checkpoints.

## 3. Carry the plan through the real stages

| Stage | Production handoff |
|---|---|
| Proposal | Show which reference functions are retained, changed or unavailable. Bind the selected pipeline, speech architecture and full-run review scope. |
| Script | Write and review the whole spoken story first. Map sections to beat IDs; each section advances the story. Read/review it continuously for spoken phrasing, repetition, meaning and ending. Do not write one interchangeable reminder per provider clip. |
| Scene plan | Map each shot to a beat and its actual script section. Describe action, delivery/gesture intent, opening/closing state and connection to adjacent shots. Provider clip length is a material constraint, not the narrative clock. |
| Assets | Prompts consume the approved script and scene plan, including neighboring delivery and action states. Preserve the story when repairing pronunciation; simplify phrasing locally rather than substituting generic filler throughout the film. |
| Edit | Choose cuts from actual speech/action windows. Use inserts to illustrate the spoken point, preserve speech across visual cuts when appropriate, and inspect room-tone/voice joins. Keep sentence endings and natural holds. |
| Compose | Inspect the exact continuous preview against the adaptation plan. Record reference fidelity, script coherence, performance, continuity and technical results separately. |

Use existing canonical metadata to store section/scene-to-beat mappings and
the approved adaptation reference. Each director reads that plan and the prior
artifact, then produces the next artifact from them. Keep production decisions
in the existing decision log where needed. Do not add a separate reference
checklist, checkpoint result or approval step at every stage.

### Write the film before splitting generation requests

Draft the complete spoken text as one conversation. Make each passage add a new
piece of information, resolve a prior question or lead into the next action.
Only then divide it into script sections and feasible generation units. Timing
is estimated from the target language and intended delivery, then refined from
the actual audio. A short Chinese sentence must not be padded to a ten-second
clip with idle smiling merely because ten seconds were generated.

Script sections, generation units and edit shots are different boundaries.
One section may need several visual shots; one continuous performance may serve
several sections. Keep enough head/tail material for editing, without directing
a fresh greeting and closing smile for every unit.

### Direct one person through the whole film

Carry a stable role, voice strategy, wardrobe and setting, with an evolving
performance. Tie each gesture to a spoken idea or visible task; use a relaxed
rest position between actions. Tell the next shot whether the speaker is
continuing an explanation, reacting, demonstrating or ending the film. Specify
the outgoing gaze, hand/prop position and posture when a visible action carries
across the cut. Reserve the closing gesture for the actual ending.

For external narration, generate coherent passages with the same selected voice
and delivery settings; use actual narration timing to place visual changes.
For visible speech, use the approved native-dialogue or lip-sync route. A still
identity reference anchors appearance, not voice. If supported by the selected
route, reuse an authorized voice reference or continuation input. When it cannot
provide either, plan meaningful B-roll between independent performances and
carry ambience across those visual cuts; this reduces visible resets but cannot
make differing voices identical. Never silently substitute TTS for native speech.

### Build transitions from meaning and performance

Choose inserts at the word or action they explain. Let the existing dialogue
continue over an insert; return to the presenter at the next meaningful point,
not at an arbitrary fixed offset. Trim unnecessary lead-ins and completed
closing holds, retain intended pauses and breaths, and join compatible room
tone separately from speech. Do not crossfade voiced syllables or use a dissolve
to hide an unfinished sentence. Provider clip lengths are source ranges, not
automatic final shot lengths.

For example, a preparation-to-handoff passage could be directed as follows
(illustrative working notes, not an additional artifact):

| Spoken progression | Performance | Edit connection |
|---|---|---|
| "先把这批货的清单理出来。" | Presenter introduces the task, one small indicating gesture. | Cut to the list when it is mentioned; the same speech continues. |
| "照着清单核对箱数，再看包装有没有破损。" | Continue the explanation without another greeting or closing smile. | Show counting then packaging; preserve the spoken connection between them. |
| "交接时把数量和货物情况记下来，这一批就有了清楚的记录。" | Resolve the setup with a calmer, deliberate close. | Show the handoff record, then return for the actual ending. |

## 4. Review the actual sequence during full production

The complete scene-plan board is the human production gate. Do not create a
separate sample approval or wait for one. After approval, inspect generated
adjacent beats and transitions as they become available in the full run.
Check voice/delivery consistency, lip sync where promised, posture/action joins,
speech flow, rhythm and ambience. Repair only failed leaves; preserve accepted
sibling clips. A plan approval is not evidence that these actual-media checks
passed. Material changes to the confirmed architecture require user direction.

## 5. Keep intent independent from performed output

Compare actual speech to the approved script before editing either. Keep the
raw transcript and approved wording. Accept a harmless variation only after a
semantic and spoken-language review, recording the reason and revised artifact.
Do not rewrite the expected script merely to raise a matching score. Changed
meaning, awkward phrasing, missing content or repetitions require a targeted
repair, or an explicitly disclosed deviation under existing policy.

At final review, distinguish technical validity from creative acceptance. Whole
frame review can cover visual defects but cannot pass audible naturalness,
voice continuity or temporal lip sync. Record absent listening/playback evidence
as `unverified`, not `pass`. Use existing delivery promises and approval policy
to resolve material gaps; do not silently claim complete creative acceptance.

## Completion boundary

Complete only the applicable requirements with source-bound evidence. Preserve
unknown provider attempts, accepted siblings and prior artifacts. At existing
revision limits report unresolved findings; do not erase them by adopting the
failed output or inventing a review. Do not turn a process repair into a new
production, paid retry, provider switch, upload or publication.
