# Same-input composition verification

Full 30-second, 720x1280 composition; approved existing seven-shot media, narration, music, transcript, source and parameters reused. No providers called. Outputs isolated from historical project.

| Automatic stage | Previous flow | New flow |
|---|---:|---:|
| Render | 74.091 s | 69.979 s |
| Final review | 13.220 + 12.956 s | 12.423 s |
| Preflight | none separately | 0.466 s |
| Full decode | 0.711 s | 0.751 s |
| Accepted-preview finalization | none | 0.379 s |
| Total measured | 101.012 s | 85.136 s |

Observed single-pass reduction: 15.7%. Render difference includes execution/cache variance. The reliable structural benefit is removal of one duplicate final review and no second render at finalization. Both old and new render exactly once in this baseline.

All output MP4 bytes match; all 900 decoded frames match. The final file is byte-identical to its accepted preview. Twelve full-sequence sheets were inspected. Changed timeline refuses finalization and creates no output. Historical source/final hashes remain unchanged.

This comparison starts from completed corrected composition source. It does NOT prove improvement in model authoring time, asset-generation latency, end-to-end Feishu delivery, or the earlier 22-minute total. Visual review wall time is excluded from both automatic timings. No perceptual audio audition was performed in this benchmark; automated audio/transcript review passed.
