# CBSC-ZDC v2 final QA report

**Audit date:** 2026-07-23  
**Scope:** executable Python scaffold, mathematical LaTeX specification, bibliography integration, PDF construction, and repository packaging.  
**Status:** structurally audited research specification; **not** a trained or Geant4-validated simulator.

## 1. Final commands and results

### Python syntax and importability

```bash
PYTHONPATH=src python -m compileall -q src tests scripts
```

Result: **PASS**.

### Unit and property tests

```bash
PYTHONPATH=src pytest -q
```

Result:

```text
30 passed, 7 warnings in 1.01 s
```

The seven warnings are the same PyTorch performance warning: nested-tensor optimization is disabled because the reference `TransformerEncoderLayer` uses `norm_first=True`. No warning reports NaN, an assertion failure, an invalid tensor, or a numerical discrepancy. The production timing study should profile pre-norm and alternative implementations rather than suppressing the warning.

### Coverage

```bash
PYTHONPATH=src coverage run --branch -m pytest -q
coverage json -o coverage.json
coverage report -m
```

Result:

```text
980 measured statements
132 measured branches
0 missed statements
0 missed branches
100% measured statement/branch coverage
```

All importable source modules and all tests appear in the final report, including the compatibility export, ROOT-adapter error/fake-inspection paths, and flow-matching utilities. Coverage proves that these code paths executed under synthetic tests; it does not establish physics fidelity, statistical calibration, real ROOT decoding, Vertex reliability, or deployment performance.

### Synthetic smoke sample

```bash
PYTHONPATH=src python scripts/smoke_train.py --nodes 65 --steps 1
```

Result:

```text
nonfinite                         0
negative                          0
dust_cells                        0
total_over_incident               0
accounting_identity_max           0.0
support_count_mismatch_max        0.0
resolved_layer_mismatch_max       0.0
```

This verifies the algebraic identities on one untrained synthetic sample only.

## 2. Mathematical-contract QA

The LaTeX paper and source implement the following distinction.

1. Individual longitudinal deposits `D_l` are **not** required to decrease with depth.
2. The accounting remainder

```text
R_l = T - sum_{j<=l} D_j
```

is non-increasing because all layer allocations and the reserve are nonnegative and sum to `T`.
3. The bounded response form `T = E_inc * rho`, `rho in [0,1]`, is permitted only when the audited target is raw deposited energy for which that support is correct.
4. The anti-dust decoder uses a generated finite count and exact support. In thresholded mode,

```text
E_i = tau + (D_l - K_l*tau) * softmax(r)_i
```

for selected cells; unselected cells are exactly zero. If `D_l < tau`, the budget becomes a layer-level subthreshold residual rather than artificial positive cell dust.
5. Exact Top-k does **not** prevent count inflation. A count model could request every valid cell and remain algebraically valid. The count distribution, support ranking, generated-count exposure, occupancy calibration, and positive-hit spectrum therefore require separate training objectives and reporting.
6. Hard Top-k is a sampling/evaluation decoder and is not falsely described as differentiable through selected indices. Training requires supervised support/count losses or a declared relaxation.

The paper includes propositions and proofs for the accounting and anti-dust identities. Those proofs establish only the stated algebra under their assumptions.

## 3. Source-level audit

`audit/LINE_BY_LINE_AUDIT.md` inventories every nonblank line in:

- `src/**/*.py`;
- `tests/**/*.py`;
- `scripts/**/*.py`.

Every line has a file SHA-256 and one of these labels:

- `STATIC+EXECUTED`;
- `STATIC+MANUAL`;
- `DOC/COMMENT`.

Blank separator lines are counted in physical-line totals but omitted because they carry no executable or semantic content. The ledger is not presented as a formal-verification proof.

## 4. Claim traceability

`audit/CLAIM_TRACEABILITY.md` maps major paper claims to one of:

- primary literature or official documentation;
- prior project audit evidence;
- an algebraic derivation;
- a proposed design hypothesis;
- an explicit limitation.

The 600-entry research catalogue is retained as a contribution/discovery map with evidence-depth labels. It is not misrepresented as 600 independent full-text replications.

## 5. LaTeX and PDF QA

### Build

```bash
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  CBSC_ZDC_Auditor_Specification.tex
```

Result: **PASS**, 26 A4 pages.

### Log review

- Undefined citations: **0**.
- Undefined cross-references: **0**.
- Overfull boxes: **0**.
- Underfull boxes: **18**, confined to narrow table cells; rendered review found no clipping or overlap.
- Fatal LaTeX errors: **0**.

### Structural inspection

- PDF version: 1.7.
- Encrypted: no.
- Pages: 26.
- Page size: A4, consistent on all pages.
- Form fields: none.
- JavaScript: none.
- Link annotations: 214.
- Top-level outline items reported by `pypdf`: 34.
- Fonts: embedded Latin Modern/AMS fonts.
- Metadata: title, author, subject, and keywords populated.

### Visual inspection

All 26 pages were rendered at 120 DPI and reviewed as a contact sheet. Additional attention was given to:

- title and assurance statement;
- table of contents;
- architecture diagram;
- longitudinal propositions and proofs;
- event-support and anti-dust theorem;
- the section explaining what exact Top-k cannot guarantee;
- loss definitions;
- data/ROOT plan;
- Vertex experiment table;
- implementation tensors and pseudocode;
- bibliography and auditor checklists.

No visible clipping, overlap, blank-content page, missing figure, or broken table was observed.

## 6. Final artifact hashes

```text
a2277c239fee70de876ce25bcdcac83d655a54305b8149aa100b0a28a0830b76  paper/CBSC_ZDC_Auditor_Specification.pdf
c9b32015a73fd3e1a19ce59004ddaaecc2fce7994191646c13e55ad8b0ff888f  paper/CBSC_ZDC_Auditor_Specification.tex
3447ef9f6d57beba3710134524ec7fefb5729a84ec913b1db9c1d883c471d5c7  paper/references.bib
5c177e7ec6aa601bcbb65d4f646cde3b01e5db82e3d9b0bf3bdd5d937e1f8908  FULL_CHRONOLOGICAL_RESEARCH_LOG.md
496ca7d5a1a326ebb2e062cd7b9b19e83f7fade95fcf86b7a2b6f6ac826768d8  audit/FULL_CHRONOLOGICAL_RESEARCH_LOG_V2.md
e500fd7c83d88ab2d35bdd99969b52c675efb434b4349f5f67a868758f8eae89  audit/LINE_BY_LINE_AUDIT.md
b94c4eceec2c446e2c24aad63ffd8d62acfc38310a23739814f8369958a9a165  audit/CLAIM_TRACEABILITY.md
fac1b5e842d6f4955cd3eea6aaba981919c1adfc9c04b7a8bf46a3feb6377d79  coverage.json
```

## 7. Known limitations that remain

1. **No trained model:** no claim of response, resolution, morphology, diversity, reconstruction, or speed closure is made.
2. **ROOT adapter is intentionally incomplete:** exact branch names, units, sentinel meaning, channel codec, event grouping, threshold definition, and geometry provenance must be frozen before production conversion.
3. **Attached sample not treated as authoritative physics distribution:** it came from a different Geant4 run and is used only as a structural reference.
4. **p4-only support:** independently varying entry position, vertex, detector state, material, particle species, or pileup cannot be represented unless fixed, derivable from p4, or introduced as an explicitly modeled stochastic/environmental variable. Training over 0–300 GeV does not simulate pileup; pileup is a multi-particle superposition problem.
5. **Target support assumption:** the strict total-energy bound requires confirmation for the exact stored target. Digitized or calibrated signals may require a different codec.
6. **Threshold semantics:** `tau` must come from detector/readout or a frozen analysis definition, not from whichever value improves validation loss.
7. **Count-model dependence:** exact Top-k prevents dense dust only conditional on `K_l`; count inflation remains an empirical failure mode to monitor.
8. **Graph validity:** every valid readout node and edge type must be audited against physical geometry/ganging. A graph model is retained only as a comparison, not presumed superior.
9. **Staged exposure:** training with truth profiles/counts and sampling with generated profiles/counts can still create exposure mismatch. The plan therefore includes truth/generated cross-combinations and later generated-condition fine-tuning.
10. **Solver and latency:** Euler integration is a transparent reference, not a production optimum. Step count, solver, precision, batching, and distillation require matched testing.
11. **Synthetic coverage:** 100% measured code coverage does not cover numerical behavior at production scale, GPU mixed precision, distributed training, real GCS I/O, or physics validity.
12. **Literature depth:** core sources were checked more deeply; long-tail catalogue entries have explicit abstract/metadata screening labels and should be upgraded individually when they become central to a claim.

## 8. Final assurance

An implementation that follows the frozen data contract and mathematical decoder should produce an auditable and falsifiable FastMC experiment with exact structural identities. It should not reproduce the catastrophic support errors of the previous unbounded/dense designs if the stated assumptions are satisfied. Whether the learned conditional distribution is accurate, fast, and useful remains an empirical research result, including the possibility of a defensible negative result.
