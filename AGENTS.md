# Agent Operating Contract

1. Read `docs/IMPLEMENTATION_GUIDE.md` before executing commands.
2. Treat `legacy/` as evidence only; never import or train from it.
3. Never hand-edit a frozen configuration.
4. Never use test data for preprocessing, thresholds, loss weights, architecture, stopping, or checkpoint selection.
5. Stop on schema, geometry, hash, invariant, nonfinite, or empty-bin failure.
6. Do not describe a synthetic test pass as physics validation.
7. Record every command, input hash, output hash, environment, correction, and failed attempt in an evidence log.
8. Do not log private hidden chain-of-thought. Log evidence, alternatives, decisions, counterexamples, and verification steps.
9. Use the exact stage order and shared-encoder rules in the guide.
10. Use three seeds for each frozen final condition.
11. Report all seeds and all failed gates.
12. Do not weaken a baseline, change output semantics, or omit solver/decode time.
13. Production target remains raw deposited energy unless a separately justified thresholded experiment is frozen.
14. Primary claim domain remains 50–250 GeV even when training uses 0–300 GeV.
15. The final result may be negative; scientific integrity takes priority over a pass.
