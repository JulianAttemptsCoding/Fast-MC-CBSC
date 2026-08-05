// CBSC-ZDC Fast-MC — colleague status update deck.
// Visuals-first: every content slide is built around a figure that already
// exists under exhibition/current, so nothing here is a new uncited claim.
const pptxgen = require("pptxgenjs");
const path = require("path");

const REPO = "C:/Users/Julia/Desktop/coding/ASIoP/Fast MC CBSC";
const F = (p) => path.join(REPO, p);
const OUT = process.argv[2] || "CBSC_ZDC_status_update_20260805.pptx";

// Palette matches the figures themselves: Geant4 navy, Fast-MC purple.
const NAVY = "16233A";
const SLATE = "2E4A6B";
const PURPLE = "9B4F9B";
const LIGHT = "F4F6FA";
const WHITE = "FFFFFF";
const MUTED = "6B7A90";
const AMBER = "C77D24";


// Read a PNG's intrinsic size from its IHDR chunk so figures are never stretched.
const fs = require("fs");
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
// Fit an image inside a box at its true aspect ratio, centred in the box.
function fitImage(slide, file, box) {
  const { w: iw, h: ih } = pngSize(file);
  const ar = iw / ih;
  let w = box.w, h = w / ar;
  if (h > box.h) { h = box.h; w = h * ar; }
  slide.addImage({
    path: file,
    x: box.x + (box.w - w) / 2,
    y: box.y + (box.h - h) / 2,
    w, h,
  });
  return { w, h };
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";           // 13.3 x 7.5
pres.author = "CBSC-ZDC";
pres.title = "CBSC-ZDC Fast MC — status update";

const TITLE_FONT = "Cambria";
const BODY_FONT = "Calibri";

let sectionNo = 0;

// Repeated motif: a filled circle badge carrying the section number.
function badge(slide, n, x = 0.55, y = 0.42) {
  slide.addShape(pres.ShapeType.ellipse, {
    x, y, w: 0.46, h: 0.46, fill: { color: PURPLE },
  });
  slide.addText(String(n), {
    x, y, w: 0.46, h: 0.46, align: "center", valign: "middle",
    fontFace: BODY_FONT, fontSize: 16, bold: true, color: WHITE, margin: 0,
  });
}

function contentSlide(title, subtitle) {
  sectionNo += 1;
  const s = pres.addSlide();
  s.background = { color: WHITE };
  badge(s, sectionNo);
  s.addText(title, {
    x: 1.18, y: 0.36, w: 11.6, h: 0.52,
    fontFace: TITLE_FONT, fontSize: 30, bold: true, color: NAVY, margin: 0,
  });
  if (subtitle) {
    s.addText(subtitle, {
      x: 1.18, y: 0.9, w: 11.6, h: 0.34,
      fontFace: BODY_FONT, fontSize: 13, color: MUTED, margin: 0,
    });
  }
  return s;
}

function footer(slide, text) {
  slide.addText(text, {
    x: 0.55, y: 6.95, w: 12.2, h: 0.32,
    fontFace: BODY_FONT, fontSize: 10, color: MUTED, margin: 0, italic: true,
  });
}

// Big-number callout card.
function stat(slide, x, y, w, value, label, valueColor) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 1.32, fill: { color: LIGHT }, rectRadius: 0.06,
    line: { color: LIGHT },
  });
  slide.addText(value, {
    x: x + 0.12, y: y + 0.13, w: w - 0.24, h: 0.62, align: "center",
    fontFace: TITLE_FONT, fontSize: 27, bold: true,
    color: valueColor || NAVY, margin: 0,
  });
  slide.addText(label, {
    x: x + 0.1, y: y + 0.76, w: w - 0.2, h: 0.46, align: "center",
    fontFace: BODY_FONT, fontSize: 10.5, color: SLATE, margin: 0,
  });
}

// ---------------------------------------------------------------- 1. title
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.ellipse, {
    x: 11.0, y: -1.5, w: 4.6, h: 4.6, fill: { color: SLATE },
  });
  s.addShape(pres.ShapeType.ellipse, {
    x: 12.1, y: 5.1, w: 2.6, h: 2.6, fill: { color: PURPLE },
  });
  s.addText("CBSC-ZDC Fast Monte Carlo", {
    x: 0.9, y: 2.05, w: 9.6, h: 0.9,
    fontFace: TITLE_FONT, fontSize: 42, bold: true, color: WHITE, margin: 0,
  });
  s.addText("Status update — what has changed since the last review", {
    x: 0.9, y: 3.0, w: 9.6, h: 0.5,
    fontFace: BODY_FONT, fontSize: 19, color: "C9D4E6", margin: 0,
  });
  s.addText(
    "Conditional generative shower model for the ZDC · 6,790 channels · 65 layers",
    { x: 0.9, y: 3.62, w: 9.6, h: 0.36,
      fontFace: BODY_FONT, fontSize: 13, color: "8FA3BF", margin: 0 });
  s.addText("5 August 2026", {
    x: 0.9, y: 4.35, w: 5, h: 0.34,
    fontFace: BODY_FONT, fontSize: 13, bold: true, color: PURPLE, margin: 0,
  });
  s.addText(
    "Optimization and diagnostic evidence on a validation bank. Geant4 fidelity is NOT established.",
    { x: 0.9, y: 6.35, w: 10.0, h: 0.4,
      fontFace: BODY_FONT, fontSize: 12, italic: true, color: "8FA3BF", margin: 0 });
  s.addNotes("Framing: this is a progress update, not a validation claim. The headline is that energy reconstruction now exists and is quantified against a Geant4 control, and that the loss has moved a long way — but the classifier still separates the two generators easily.");
}

// ------------------------------------------------- 2. since last time
{
  const s = contentSlide(
    "Since you last saw this",
    "Left: the state you were shown. Right: today."
  );

  s.addText("PREVIOUSLY  ·  28 July", {
    x: 0.55, y: 1.42, w: 5.9, h: 0.3,
    fontFace: BODY_FONT, fontSize: 12, bold: true, color: MUTED, margin: 0,
  });
  s.addText("NOW  ·  5 August", {
    x: 6.95, y: 1.42, w: 5.9, h: 0.3,
    fontFace: BODY_FONT, fontSize: 12, bold: true, color: PURPLE, margin: 0,
  });

  const rows = [
    ["Epochs trained", "4", "up to 40"],
    ["Best validation loss", "4.738041", "4.597152"],
    ["Energy reconstruction", "not measured", "measured, vs Geant4 control"],
    ["Per-epoch diagnostics", "none", "4,000 events every epoch"],
    ["Classifier separability", "AUROC 0.99945", "AUROC 0.8727"],
    ["Training backend", "Vertex AI, T4", "DiCOS, RTX 4090 + 3090"],
  ];
  let y = 1.8;
  rows.forEach(([label, before, after], i) => {
    const bg = i % 2 === 0 ? LIGHT : WHITE;
    s.addShape(pres.ShapeType.rect, {
      x: 0.55, y, w: 12.3, h: 0.62, fill: { color: bg }, line: { color: bg },
    });
    s.addText(label, {
      x: 0.72, y, w: 3.5, h: 0.62, valign: "middle",
      fontFace: BODY_FONT, fontSize: 13, bold: true, color: NAVY, margin: 0,
    });
    s.addText(before, {
      x: 4.3, y, w: 3.6, h: 0.62, valign: "middle",
      fontFace: BODY_FONT, fontSize: 13, color: MUTED, margin: 0,
    });
    s.addText(after, {
      x: 8.1, y, w: 4.6, h: 0.62, valign: "middle",
      fontFace: BODY_FONT, fontSize: 13, bold: true, color: SLATE, margin: 0,
    });
    y += 0.62;
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.55, y: y + 0.22, w: 12.3, h: 0.86, fill: { color: "FBF3E4" },
    rectRadius: 0.05, line: { color: "FBF3E4" },
  });
  s.addText(
    [{ text: "The two AUROC numbers are not the same measurement. ", options: { bold: true } },
     { text: "July: 40,000 test-split events, hybrid classifier, epoch-4 models. Today: 8,000 validation events, 3-seed ensemble, epoch-38 model. Read them as two studies that agree qualitatively — a classifier separates Fast-MC from Geant4 easily — not as a clean 0.999 → 0.873 delta." }],
    { x: 0.78, y: y + 0.3, w: 11.9, h: 0.7,
      fontFace: BODY_FONT, fontSize: 11.5, color: "6E4B12", margin: 0 }
  );
  footer(s, "Validation loss is the frozen weighted joint objective on the pilot validation split. Lower is better. Zero test events informed any training decision.");
  s.addNotes("The caveat box matters: do not let anyone leave thinking AUROC fell from 0.999 to 0.873 as a single tracked quantity. Different split, different sample size, different evaluator.");
}

// ------------------------------------------------- 3. loss, all families
{
  const s = contentSlide(
    "Optimization progress — all four calibrated families",
    "Every epoch ever run. Solid = training, dashed = validation."
  );
  fitImage(s, F("exhibition/current/continuation/loss_all_families_every_epoch.png"), { x: 0.5, y: 1.32, w: 12.4, h: 5.35 });
  footer(s, "Purple × marks a quarantined QA failure. Families were continued to different depths on different GPUs, so the tails are not a like-for-like comparison.");
  s.addNotes("Point out that lr3e4 (bottom left) holds the lowest loss at 4.5972, and lr1e4 (top right) has had by far the most epochs.");
}

// ------------------------------------------------- 4. running best
{
  const s = contentSlide(
    "Running-best loss — the four families side by side",
    "Each step is the lowest accepted validation loss available by that epoch."
  );
  fitImage(s, F("exhibition/current/continuation/best_validation_loss_so_far_vs_epoch.png"), { x: 0.62, y: 1.34, w: 12.1, h: 3.62 });

  stat(s, 0.62, 5.28, 2.85, "4.597152", "lr3e4 · epoch 22 · best overall", NAVY);
  stat(s, 3.72, 5.28, 2.85, "4.635220", "lr1e4 · epoch 38", SLATE);
  stat(s, 6.82, 5.28, 2.85, "4.673036", "lr1e4 half batch · epoch 21", SLATE);
  stat(s, 9.92, 5.28, 2.8, "4.843471", "lr3e5 · epoch 8", MUTED);
  footer(s, "Quarantined observations stay in the full loss figure but never advance this best-so-far trace.");
  s.addNotes("lr3e4 leads lr1e4 by 0.038. Run-to-run resolution is about 0.02, so the lead is real but no longer commanding — it was 0.105 two phases ago.");
}

// ------------------------------------------------- 5. NEW energy recon
{
  const s = contentSlide(
    "New since last time: energy reconstruction, against a Geant4 control",
    "The same frozen 6,790-channel readout adapter is run on both generators, so the Geant4 bar is the reference floor."
  );
  fitImage(s, F("exhibition/current/external_metrics/current_four_momentum_accuracy.png"), { x: 0.55, y: 1.36, w: 8.35, h: 4.75 });

  const cardX = 9.2;
  stat(s, cardX, 1.5, 3.6, "1.62×", "energy relative RMSE vs Geant4", PURPLE);
  stat(s, cardX, 3.0, 3.6, "2.52×", "energy 68% width vs Geant4", PURPLE);
  stat(s, cardX, 4.5, 3.6, "1.92×", "angular median vs Geant4", PURPLE);
  s.addText("Fast-MC mean energy response 0.9490 against the Geant4 control's 0.9941 — a −5.1% bias against −0.6%.",
    { x: cardX, y: 5.95, w: 3.6, h: 0.9,
      fontFace: BODY_FONT, fontSize: 11, color: SLATE, margin: 0 });
  footer(s, "Accepted best checkpoint, lr1e4 epoch 38. Validation events only; zero test events. Descriptive downstream evaluation — it cannot select or tune the generator.");
  s.addNotes("This is the slide colleagues have never seen. Fast-MC showers now reconstruct energy, and the degradation against a Geant4 control run through the identical adapter is roughly a factor 1.6 to 2.5 depending on the observable.");
}

// ------------------------------------------------- 6. recon vs energy
{
  const s = contentSlide(
    "Reconstruction error against incident energy",
    "The gap to the Geant4 control is widest at low energy and narrows as the shower gets larger."
  );
  fitImage(s, F("exhibition/current/external_metrics/current_four_momentum_vs_energy.png"), { x: 1.5, y: 1.36, w: 10.3, h: 4.05 });

  stat(s, 1.5, 5.62, 3.2, "0.399 → 0.195", "Fast-MC energy RMSE, 50 → 250 GeV", PURPLE);
  stat(s, 5.05, 5.62, 3.2, "0.280 → 0.137", "Geant4 control, same bins", NAVY);
  stat(s, 8.6, 5.62, 3.2, "~500 events", "per energy bin", SLATE);
  s.addNotes("Both curves improve with energy, as expected for a sampling calorimeter. Fast-MC tracks the shape but sits consistently above the control.");
}

// ------------------------------------------------- 7. classifier
{
  const s = contentSlide(
    "Can a classifier still tell the two generators apart?",
    "Yes — and this is the single most important negative result in the project."
  );

  fitImage(s, F("exhibition/current/external_metrics/current_auroc_seed_spread.png"), { x: 0.55, y: 1.4, w: 7.3, h: 4.25 });

  const cx = 8.15;
  s.addText("Today, epoch 38", {
    x: cx, y: 1.42, w: 4.7, h: 0.3,
    fontFace: BODY_FONT, fontSize: 12, bold: true, color: PURPLE, margin: 0,
  });
  const models = [
    ["Low-level hybrid, 3 seeds", "0.8727 ± 0.0117", PURPLE],
    ["High-level GBM control", "0.9291", SLATE],
    ["Condition-only control", "0.5000  (p = 1.0)", MUTED],
  ];
  let my = 1.8;
  models.forEach(([name, val, col]) => {
    s.addShape(pres.ShapeType.roundRect, {
      x: cx, y: my, w: 4.7, h: 0.78, fill: { color: LIGHT },
      rectRadius: 0.05, line: { color: LIGHT },
    });
    s.addText(name, {
      x: cx + 0.16, y: my + 0.06, w: 3.0, h: 0.66, valign: "middle",
      fontFace: BODY_FONT, fontSize: 11.5, color: SLATE, margin: 0,
    });
    s.addText(val, {
      x: cx + 2.9, y: my + 0.06, w: 1.7, h: 0.66, valign: "middle", align: "right",
      fontFace: TITLE_FONT, fontSize: 14, bold: true, color: col, margin: 0,
    });
    my += 0.9;
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: cx, y: 4.6, w: 4.7, h: 1.05, fill: { color: "FBE9E9" },
    rectRadius: 0.05, line: { color: "FBE9E9" },
  });
  s.addText("The acceptance gate is AUROC ≤ 0.65. No checkpoint the project has ever produced comes close.",
    { x: cx + 0.18, y: 4.72, w: 4.35, h: 0.82,
      fontFace: BODY_FONT, fontSize: 11.5, bold: true, color: "8C2F2F", margin: 0 });

  footer(s, "The condition-only control sits exactly at chance, so the separation comes from the calorimeter deposits and not from mismatched incident conditions.");
  s.addNotes("The condition-only control at exactly 0.5 with p = 1.0 is the important sanity check. Also note the high-level GBM beats the low-level hybrid here, which says the remaining discrepancy lives in summary shower observables, not in fine per-cell structure.");
}

// ------------------------------------------------- 8. profiles
{
  const s = contentSlide(
    "Same incident neutron, five stochastic Fast-MC showers",
    "Longitudinal energy profile for one fixed validation condition, per family. The Geant4 reference is identical in every panel."
  );
  fitImage(s, F("exhibition/current/model/10_same_condition_longitudinal_profiles.png"), { x: 0.5, y: 1.36, w: 12.4, h: 5.3 });
  footer(s, "One condition, illustrative rather than statistically representative. Note the ECAL layer-0 spike: Geant4 deposits ~10 GeV there and Fast-MC undershoots it by two orders of magnitude.");
  s.addNotes("The layer-0 undershoot is a real, visible, unresolved defect and worth raising explicitly — it is the clearest single structural discrepancy in the model.");
}

// ------------------------------------------------- 9. 3D
{
  const s = contentSlide(
    "One Geant4 shower and five Fast-MC draws, same four-momentum",
    "Lowest accepted-loss family · epoch 22 · K_inc = 133 GeV · top 1,000 cells by deposited energy per panel."
  );
  fitImage(s, F("exhibition/current/model/12_same_condition_3d_energy_deposits.png"), { x: 0.5, y: 1.36, w: 12.4, h: 5.3 });
  footer(s, "The five draws differ because the generator is stochastic. Plausible-looking events are not evidence of fidelity.");
  s.addNotes("Useful for intuition. The Geant4 panel is visibly denser and brighter in the core than any of the five draws.");
}

// ------------------------------------------------- 10. distributions
{
  const s = contentSlide(
    "Fixed-condition validation distributions",
    "50 Geant4 events against 250 conditional Fast-MC draws, best family, epoch 22."
  );
  fitImage(s, F("exhibition/current/model/11_best_model_sample_distributions.png"), { x: 0.62, y: 1.36, w: 12.1, h: 5.25 });
  footer(s, "Total response and radial RMS track well; positive-cell count and depth centroid show the largest residual disagreement.");
}

// ------------------------------------------------- 11. boundary
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("Where the evidence actually stands", {
    x: 0.7, y: 0.55, w: 12, h: 0.6,
    fontFace: TITLE_FONT, fontSize: 32, bold: true, color: WHITE, margin: 0,
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.7, y: 1.45, w: 5.85, h: 4.6, fill: { color: "1E3050" },
    rectRadius: 0.05, line: { color: "1E3050" },
  });
  s.addText("Established", {
    x: 1.0, y: 1.68, w: 5.2, h: 0.4,
    fontFace: BODY_FONT, fontSize: 16, bold: true, color: "7FD6A8", margin: 0,
  });
  s.addText([
    { text: "Production ROOT conversion, frozen geometry and graph", options: { bullet: true, breakLine: true } },
    { text: "End-to-end FP32 GPU execution, checkpoint and recovery", options: { bullet: true, breakLine: true } },
    { text: "Zero structural-invariant failures in accepted runs", options: { bullet: true, breakLine: true } },
    { text: "Short-horizon optimization improvement, four families", options: { bullet: true, breakLine: true } },
    { text: "Exact decoder: exact zeros, exact hit counts, exact layer budgets", options: { bullet: true, breakLine: true } },
    { text: "Fixed-condition validation-only visual QA and a public site", options: { bullet: true } },
  ], { x: 1.0, y: 2.2, w: 5.25, h: 3.6,
       fontFace: BODY_FONT, fontSize: 12.5, color: "D6E2F2",
       paraSpaceAfter: 8, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, {
    x: 6.9, y: 1.45, w: 5.85, h: 4.6, fill: { color: "3A2036" },
    rectRadius: 0.05, line: { color: "3A2036" },
  });
  s.addText("Not established", {
    x: 7.2, y: 1.68, w: 5.2, h: 0.4,
    fontFace: BODY_FONT, fontSize: 16, bold: true, color: "F3A0A0", margin: 0,
  });
  s.addText([
    { text: "Geant4 fidelity — AUROC 0.77–0.92 at every epoch measured", options: { bullet: true, breakLine: true } },
    { text: "Three-seed behaviour — not yet run", options: { bullet: true, breakLine: true } },
    { text: "Untouched-test performance — the split stays sealed", options: { bullet: true, breakLine: true } },
    { text: "Downstream reconstruction — first numbers exist, 1.6–2.5× the Geant4 control", options: { bullet: true, breakLine: true } },
    { text: "Diversity and memorization acceptance", options: { bullet: true, breakLine: true } },
    { text: "Fast-MC emits ~2× as many zero-response events as Geant4", options: { bullet: true } },
  ], { x: 7.2, y: 2.2, w: 5.25, h: 3.6,
       fontFace: BODY_FONT, fontSize: 12.5, color: "F0DCE6",
       paraSpaceAfter: 8, margin: 0 });

  s.addText("The loss and the distribution metrics disagree about which epoch is best. Checkpoint selection follows the validation loss, as declared, and does not switch to whichever metric flatters a run.",
    { x: 0.7, y: 6.25, w: 12.05, h: 0.6,
      fontFace: BODY_FONT, fontSize: 12, italic: true, color: "8FA3BF", margin: 0 });
  s.addNotes("Do not soften this slide. The honest position is that optimization has moved a long way and fidelity has not been demonstrated.");
}

// ------------------------------------------------- 12. running now
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.ellipse, {
    x: 11.4, y: -1.1, w: 3.6, h: 3.6, fill: { color: SLATE },
  });
  s.addText("Running right now", {
    x: 0.8, y: 0.8, w: 10, h: 0.65,
    fontFace: TITLE_FONT, fontSize: 34, bold: true, color: WHITE, margin: 0,
  });
  s.addText("An unattended campaign on two GPUs at Academia Sinica",
    { x: 0.8, y: 1.5, w: 10, h: 0.4,
      fontFace: BODY_FONT, fontSize: 15, color: "9FB4D0", margin: 0 });

  const items = [
    ["1", "lr3e4, 20 more epochs", "Absolute epochs 23–42, resuming from the epoch-22 best. Epoch 23 came in at 4.600282."],
    ["2", "Then, only if it plateaus", "If the best epoch falls more than 6 behind the latest, the campaign advances to lr1e4 half batch, then lr3e5."],
    ["3", "Diagnostics every epoch", "The second GPU generates 4,000 validation events per checkpoint and records 348 metrics, namespaced per run."],
  ];
  let iy = 2.25;
  items.forEach(([n, head, body]) => {
    s.addShape(pres.ShapeType.ellipse, {
      x: 0.85, y: iy + 0.06, w: 0.5, h: 0.5, fill: { color: PURPLE },
    });
    s.addText(n, { x: 0.85, y: iy + 0.06, w: 0.5, h: 0.5, align: "center",
      valign: "middle", fontFace: BODY_FONT, fontSize: 15, bold: true,
      color: WHITE, margin: 0 });
    s.addText(head, { x: 1.6, y: iy, w: 10.8, h: 0.36,
      fontFace: BODY_FONT, fontSize: 16, bold: true, color: WHITE, margin: 0 });
    s.addText(body, { x: 1.6, y: iy + 0.38, w: 10.8, h: 0.62,
      fontFace: BODY_FONT, fontSize: 12.5, color: "AFC1D8", margin: 0 });
    iy += 1.28;
  });

  s.addText("The largest untested lever remains the training bank: every result here uses 26,624 events, which is 4.3% of the available training data.",
    { x: 0.85, y: 6.25, w: 11.6, h: 0.6,
      fontFace: BODY_FONT, fontSize: 12.5, italic: true, color: PURPLE, margin: 0 });
  s.addNotes("If asked what would most likely move fidelity: the pilot bank is 4.3% of the corpus and has never been increased.");
}

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
