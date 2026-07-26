# Five-minute pitches

## General science-fair judge

Simulating one neutron in a detailed detector can require tracking many interactions and secondary particles. That is accurate but expensive. My project learns the distribution of detector responses already produced by Geant4, so researchers can generate many statistically realistic showers faster.

The key idea is to split the problem into understandable parts. First, the model receives only the neutron's four-momentum: its energy and direction. It predicts a physically bounded total response. Then it allocates that response through detector depth while keeping an exact remaining-energy budget. It does not force every deeper layer to contain less energy, because real neutron showers can begin late and grow before fading. Finally, a conditional generative model places each layer's assigned energy among the detector cells while respecting exact nonnegative energy sums.

I will train on non-pencil-beam neutron simulations from 0 to 300 GeV and report the main results from 50 to 250 GeV. I will compare this structured model with simpler empirical, single-stage flow, non-graph and existing ZDC models. I will report where it reproduces Geant4 well, where it fails, how diverse its showers are, and how fast it runs. The project does not replace Geant4 physics; it builds a faster surrogate for the specific detector and simulation configuration represented in the data.

## Computational physicist in HEP

We propose a conditional readout-level surrogate for single-neutron ZDC response with p4 as the sole raw event condition. The target is the joint distribution over 400 ECAL and 6,390 HCAL channels in a frozen geometry. The design combines established components: a minimal p4 encoder and shared event latent; optional no-response and first-visible-layer hazard heads; a bounded response-ratio mixture; stick-breaking longitudinal budgets; a layer count model; and a parallel all-layer conditional flow or flow-matching field with static geometry features. Per-layer energies are not constrained to decrease. Only the remaining budget is monotone, preserving shower maxima, late starts and secondary structure while guaranteeing nonnegative exact energy closure for an audited raw-deposit target.

The experiment trains on the full 0-300 GeV support but reports 50-250 GeV as the primary domain, with a matched 50-250-only ablation. Comparisons include a competent empirical profile model, the supplied single-stage graph-flow baseline, a matched non-graph flow, a response-regime mixture and a serial layer model as an ablation. External references include Wojnar's full and latent ALICE ZDC flow-matching implementations, the broader ALICE ZDC generative repository and ExpertSim.

Training monitoring emphasizes free-running conditional distributions rather than likelihood alone: response mean/width/quantiles, zero response, ECAL/HCAL sharing, layer covariance, late energy, counts, spatial moments, high- and low-level C2ST, diversity/coverage, memorization, downstream reconstruction and decomposed timing. The immediate deliverable is an executable research scaffold and a Vertex pilot; it is not claimed as a validated simulator.
