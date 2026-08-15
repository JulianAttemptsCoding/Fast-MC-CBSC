# v3 checkpoint format-4 save path — fixed 2026-08-15

Phase B. Release-blocking v3 software defect. No training launched, no paid
compute, test split not opened.

`PHYSICS VALIDATION NOT ESTABLISHED`.

## Root cause

`save_checkpoint` has supported format 4 since the v3 overlay landed. **Nothing
ever called it with `architecture_version`.** All three trainer save sites —
`best.pt`, `last.pt`, and the mid-epoch `progress.pt` — passed only the
format-3 positional arguments, so the helper took its format-3 early return for
every run regardless of the declared architecture.

**Why the existing tests missed it.** `tests/test_v3_checkpoint_resume.py`
exercises `save_checkpoint` directly and supplies `architecture_version` itself.
It proved the helper correct while the production caller was not. A helper test
cannot observe an argument its caller never passes.

**Consequence.** S1-axis is a correct v3 run whose checkpoints record
`architecture_version: null` and omit every format-4 field. The blast radius was
every v3 row that would have followed — including the D1 and D2 critic arms,
whose resume depends entirely on those twelve fields.

## Fix

`trainer.v3_checkpoint_fields(config)` returns `{}` when the architecture
resolves to `cbsc-zdc-v2.2` — including when the key is absent — which keeps
`save_checkpoint` on its format-3 early return and every historical checkpoint
byte-identical. Under `cbsc-zdc-v3` it returns the full twelve-field set with
the adversarial slots null.

It is derived **once per run**, beside `provenance`, so `best.pt`, `last.pt` and
`progress.pt` cannot disagree about the run's architecture identity. Deriving it
at each save site is how the original defect was possible.

New guard `checkpoint.require_adversarial_resume_source()` rejects any format
other than 4, a format-4 claim missing a required field, and a null
`architecture_version`. It explicitly still permits loading a format-3
checkpoint for **evaluation and weight-only initialization** — it governs
adversarial resume only.

## The S1 checkpoint was not touched

```
before  2235774417fcb916ab3becbfe3eef985bbd90e0ee24a090174736de5afd9ae31
after   2235774417fcb916ab3becbfe3eef985bbd90e0ee24a090174736de5afd9ae31
```

Re-hashed on the pod after the fix. It is not re-stamped, re-saved, or migrated
to satisfy the new guard. If a format-4 derivative is ever needed it must be a
new provenance-linked file with a new hash and proved tensor equality — never a
replacement of the original bytes.

## Tests

36 new tests in `tests/test_v3_checkpoint_format_integration.py`, all driving
`train_from_config` — the real production entry point — and inspecting the bytes
it actually wrote.

They cover: format 4 and the exact version string on a v3 run; a never-null
`architecture_version`; each of the twelve required fields, one parametrized
test per field; valid types and present-but-null adversarial slots; format 3 and
its **exact** key set preserved for v2.2 and for an absent declaration; no
format-4 field leaking into a v2.2 checkpoint; the helper's emitted field set and
its carried envelope hash, support temperature and contract hash; a bit-exact
round trip; a bare v3 declaration leaving trained weights bit-identical to the
v2.2 run; a v3 row initialized from a v3 checkpoint being itself format 4; the
resume guard accepting format 4 and rejecting format 3, missing fields and a null
version; `critic_state` failing closed without either `architecture_version` or
`experiment_contract_sha256`; and the screening registry's record of S1 as
format 3, non-resume, immutable.

## One wrong premise, caught and corrected

The first version of the "v2.2 and bare v3 agree" test asserted **identical**
state-dict key sets. It failed. The cause was not the code: a v3 model always
registers `response_envelope_caps_gev`, and with no envelope supplied it is
`torch.zeros(0)` while `response_cap_for` falls back to the v2.2 cap rule.

The assertion now proves the property that actually matters — every shared
tensor bit-identical, the only extra entry `response_envelope_caps_gev`, and
that buffer asserted to hold **zero elements** in a separate test. A subset
assertion alone would have let a genuine behavioural change hide behind it.

## Verification

```
python -m compileall -q src vertex scripts tests exhibition     exit 0
PYTHONPATH=src python -m pytest -q                              634 passed  (598 -> 634, +36)
python scripts/v3_resume_soak.py --updates 32 --stop-at 16      max abs diff 0.0 vs gate 1e-6
                                                                contract hash verified
                                                                replay manifest verified
                                                                critic/generator counts restored at 16
python scripts/verify_v3_run.py --mode software                 status pass, 17 test files
                                                                absent version means v2.2
                                                                v2.2 loss keys unchanged (9)
```

The suite total is reported as measured each phase. It is not hard-coded as a
final expected value anywhere in the test suite.
