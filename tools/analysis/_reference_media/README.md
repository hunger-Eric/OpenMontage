# Migrated reference-media implementation

Source: `@hypit/hypit` 0.2.6, `packages/video-cli/src/`.
Copyright and license: see `LICENSE` and `../../../third_party/hypit/PROVENANCE.json`.

`media.ts`, `transcript.ts`, and `process.ts` contain the migrated implementation.
The only source adaptation removes fetch/prepare-fetch and their yt-dlp dependency,
and supplies the original type-only `CliIo.write` contract locally. No inspection,
timestamp, layout, transcript, phrase matching, or difference-scoring algorithm was
replaced. `runner.ts` is the repository-local process boundary; it does not invoke
or resolve a Hypit executable or distribution.

Install the pinned original dependencies with `npm ci --prefix tools/analysis/_reference_media`.
Use the registered `reference_media` tool or `video_analyzer` from OpenMontage.
