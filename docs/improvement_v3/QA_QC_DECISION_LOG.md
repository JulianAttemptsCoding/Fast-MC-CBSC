# QA/QC decision log

This is an auditable record of evidence, alternatives, decisions, and fastest
falsification checks. It intentionally excludes private chain-of-thought. No
unrun idea is reported as an observed improvement.

| # | Intervention | Evidence or risk | Fastest decisive check | Disposition |
|---:|---|---|---|---|
| 1 | Finish/reconcile corrected LR anneal | inherited six-epoch `T_max` produced a 12-epoch sawtooth | terminal scheduler/log trace | required before causal comparisons |
| 2 | Preserve v2.2 path | many frozen configs/checkpoints have scientific identity | fixed-seed old-config equivalence | required |
| 3 | Add v3 architecture switch | new heads change state/config schemas | old/new schema unit tests | required |
| 4 | Train final model on full train split | current evidence uses only 4.3% pilot bank | matched pilot/full learning curves | required for final |
| 5 | Three generator seeds | evaluator seeds do not measure training variance | seeds 20260723–25 | required for final |
| 6 | Incident-axis node coordinates | audited node fields use only global static geometry | rotation/basis tests plus off-axis validation | high priority |
| 7 | Add event entry point as input now | current production contract says fixed vertex and provides no varying entry input | vertex-variance audit | reject unless contract changes |
| 8 | Preserve exact decoder | core support/count/nonnegative/closure guarantee | invariant tests | required |
| 9 | Bounded positive spline | current positive branch can create a second zero | zero-cause and spline round-trip tests | high priority |
| 10 | Reuse quantile safety cap as hard spline support | quantile cap may not contain all truth | full training exceedance scan | rejected |
| 11 | Train-only max-envelope support | bounded model needs guaranteed training support | full rescan `0<T<C(K)` | selected, with validation out-of-support reporting |
| 12 | Visibility temperature only | cannot fix second zero atom | decompose zero causes | diagnostic only |
| 13 | Focal/class-weighted visibility | can alter physical prevalence | calibration comparison | defer |
| 14 | Hierarchical ECAL/HCAL first layer | rare layer-0 deficit in flat 65-way task | truth-forced prevalence/calibration | high priority |
| 15 | Focal ECAL loss immediately | may improve recall but distort prevalence | unweighted likelihood first | defer |
| 16 | Span-plus-gaps activity | compact and fast if gaps are rare | train gap-count/length statistic | primary if compact fraction >=0.99 |
| 17 | AR activity | independent Bernoulli misses transitions | free-running transition/correlation comparison | primary if compact rule fails; matched ablation otherwise |
| 18 | AR counts | independent counts miss adjacent/long-range dependence | conditional count-correlation matrix | high priority |
| 19 | Joint monolithic 65-layer categorical state | state space is combinatorial and hard to audit | complexity/latency estimate | reject |
| 20 | Keep existing profile flow first | it is differentiable and structurally compatible | controlled v3 baseline | selected |
| 21 | OT-CFM for profile | literature reports simpler flows, but conditional masks complicate pairing | matched coupling ablation | screen later |
| 22 | OT-CFM across share supports | incompatible hard masks make pairs physically ambiguous | identical-support grouping coverage | defer/reject default |
| 23 | Increase width/depth | no full-data underfit proof | capacity scaling after full baseline | reject for now |
| 24 | Shared event latent everywhere | heads may ignore it; adds identifiability problem | latent sensitivity/MI proxy | defer |
| 25 | Calibrate Gumbel temperature | audited noise can dominate learned logits | repeated-draw topology/diversity grid | high priority |
| 26 | Deterministic support only | may improve recall while destroying stochastic diversity | repeated-identical-p4 comparison | not a default; diagnostic endpoint only |
| 27 | Pairwise edge loss now | topology failure not yet localized | edge/distance residual after earlier fixes | trigger-only |
| 28 | Graph-Laplacian loss now | can reward wrong smoothness and conflict with sparse physics | Laplacian metric and gradient cosine | trigger-only |
| 29 | Layer-correlation loss now | minibatch estimator is noisy | truth-half and batch-size stability | metric first |
| 30 | Full classifier through current `sample()` | `no_grad` plus discrete draws blocks pathwise gradient | intended-module gradient test | rejected |
| 31 | Remove only `@torch.no_grad()` | Bernoulli/categorical/sort/Boolean top-k remain nondifferentiable | autograd graph inspection | rejected |
| 32 | D1 share-only critic | clean gradient path under truth structure | gradient-isolation test | first critic experiment |
| 33 | D2 profile-only critic | clean 65-dimensional gradient path | gradient-isolation test | second critic experiment |
| 34 | D3 support critic immediately | requires validated structured estimator | topology trigger + estimator QA | conditional later |
| 35 | Full relaxed shadow sampler | changes every discrete variable and semantics | only after D1–D3 replicate | long-term defer |
| 36 | Projection conditioning | critic must judge `p(shower|p4)` not marginal shower law | condition-shuffle test | selected |
| 37 | Unconditional critic | can accept wrong p4-to-shower mapping | conditional control | rejected |
| 38 | Continuously updated live critic | avoids 20-epoch cold-restart shocks | reset-vs-continuous control if needed | selected |
| 39 | Reset critic every 20 epochs | loses boundary and creates nonstationarity | monitor loss across reset | rejected default |
| 40 | Freeze one critic forever | becomes stale/exploitable | accuracy versus generator age | rejected |
| 41 | Store all generated history | unbounded and obsolete failures dominate | age-conditioned accuracy/memory | rejected |
| 42 | Use only best-epoch fakes | stale and enables cycling | fresh-only critic score | rejected |
| 43 | Fresh/recent/anchor replay | history precedent while keeping current samples dominant | composition/age ablation | selected |
| 44 | 65,536 final replay capacity | prior proposal; dense storage can be large | measured >1 GiB threshold then sparse CSR | selected final, 8,192 pilot |
| 45 | Live critic on separate 3090 from first run | filesystem transport cannot carry autograd and introduces staleness | single-process correctness baseline | rejected first; async ablation later |
| 46 | L40S single-process critic | exact synchronized update and autograd | one-step/full-resume test | selected first |
| 47 | Direct non-saturating classifier loss | literal proposed idea, but can destabilize | D1/D2 matched screen | selected ablation |
| 48 | Critic feature matching | potentially smoother learned-statistic target | matched direct-vs-feature screen | selected control |
| 49 | Make classifier loss dominant | risks metric gaming and physics regression | gradient ratio/cosines | rejected |
| 50 | Measured 5/10/20% gradient targets | interpretable stage-local strength | matched screen | selected |
| 51 | Automatic GradNorm/PCGrad/ConFIG | not guaranteed; recent calorimeter result reports regressions in one setting | direct matched ablation only | not default |
| 52 | Spectral normalization | lightweight critic stabilization precedent | logit/gradient monitor | selected |
| 53 | R1 regularization | convergence/stability support near real data | gamma screen if instability | selected default gamma 1 |
| 54 | WGAN-GP as default | finite-update convergence not universal and changes objective | logistic-R1 control first | alternative only |
| 55 | PacGAN | useful only if diversity collapses | repeated-condition diversity | contingency |
| 56 | Unrolled GAN | high compute/complexity | only after simpler controls fail | defer |
| 57 | SIMPLE exact-forward estimator | directly targets k-subset gradients | tiny-layer enumerated bias/variance | D3 candidate |
| 58 | Straight-through Gumbel top-k | uncontrolled bias | compare with SIMPLE/finite difference | rejected default |
| 59 | External C2ST inside training | leaks evaluator and invalidates independent evidence | import/data-boundary test | prohibited |
| 60 | Separate critic monitor | detects overfit/staleness without validation leakage | disjoint-role evaluation | required |
| 61 | 90/5/5 exact train-role partition | clean critic data roles; exact control needed for lost generator data | partition manifest assertions | selected |
| 62 | Use validation/test in replay | contaminates model development | ID intersection assertion | prohibited |
| 63 | C2ST-only selection | classifier-specific blind spots | multi-metric Pareto/guard rule | rejected |
| 64 | Add topology/correlation metrics | current suite undermeasures joint structure | truth-half floors | required before relevant changes |
| 65 | Add diversity/memorization | critic can collapse or memorize | repeated p4 and nearest-neighbor floors | required |
| 66 | Frozen neural p4 utility model | differentiable downstream relevance | ensemble/generalization audit | later metric/weak ablation |
| 67 | Existing XGBoost directly in loss | nondifferentiable | gradient test | impossible as written |
| 68 | Train p4 predictor on fakes | moves target toward generator | data provenance assertion | rejected |
| 69 | Angular p4 loss regardless of data | fixed/near-fixed directions cannot identify angular response | direction covariance audit | conditional only |
| 70 | Postprocessing network | may hide upstream defects and add latency | only after causal fixes | backup only |
| 71 | Mixture of experts now | can fragment data and create routing boundaries | residual regime clustering after full baseline | contingency |
| 72 | Replace CBSC with latent FM | loses exact structural semantics | matched external baseline | benchmark, not fix |
| 73 | Replace CBSC with diffusion | relevant ZDC baseline but different speed/structure | same-data matched benchmark | benchmark only |
| 74 | Full-physics validation immediately | single-shower fidelity remains poor | pass/freeze single-shower protocol first | defer, then require |
| 75 | Test-set iteration | invalidates final selection evidence | access manifest | prohibited |
| 76 | Paid Vertex jobs | historical budget is stale | new user-approved cost cap | prohibited without approval |

## QC revisions from the earlier proposal

1. The exact implementation no longer assumes the quantile-derived response
   safety cap is a valid hard support. It builds and verifies a separate
   train-only maximum envelope.
2. The first live critic runs on the L40S in the generator process. The 3090
   remains valuable for external diagnostics, but a separate-pod critic is an
   asynchronous/staleness experiment rather than a clean first implementation.
3. Incident-axis features and support-temperature calibration are explicit
   supervised priorities before any support critic.
4. The active repository’s L40S/3090 topology supersedes older 4090/3090 text.
5. The final gates use the actual audited `configs/gates_primary.yaml` values;
   stricter numbers from earlier planning are not silently substituted.

