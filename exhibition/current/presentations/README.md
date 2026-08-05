# Current status-update slide decks

Decks built for people outside the day-to-day work. Everything in them is
rendered from figures that already exist under `exhibition/current/`, so a deck
never introduces a claim the exhibition cannot back.

Decks are cataloged and hashed by `exhibition/build_metrics_catalog.py` like any
other graphic. A truncated or half-written deck fails the build rather than
sitting here looking like evidence.

## `CBSC_ZDC_status_update_20260805.pptx`

| | |
|---|---|
| Built | 2026-08-05 |
| Slides | 12 |
| SHA-256 | `cfb3acc0e5166e74ced10be015359bb12ca2ebc2aa8981c36042d5cad80d785b` |
| Generator | `exhibition/build_status_update_deck.js` |
| Audience | Project colleagues who last saw the 2026-07-28 state |

**What it updates.** The previous review showed the model running and the C2ST
study's AUROC of `0.99945`, and showed no energy reconstruction at all. This deck
adds the four-family loss progression through epoch 40, the first downstream
four-momentum reconstruction measured against a Geant4 control run through the
identical readout adapter, the current low-level C2ST monitor, and the
same-condition profile, 3D and distribution comparisons.

**One thing the deck is careful about, and any future version must stay careful
about.** The July `0.99945` and today's `0.8727` are *not* the same measurement:
July used 40,000 test-split events with a hybrid classifier against epoch-4
checkpoints; today uses 8,000 validation events with a 3-seed ensemble against an
epoch-38 checkpoint. Slide 2 says so explicitly. They agree qualitatively — a
classifier separates Fast-MC from Geant4 easily, far above the 0.65 acceptance
gate — but they are two studies, not one tracked quantity, and presenting them as
a clean delta would be wrong.

**Boundary carried on the title and closing slides.** Optimization and diagnostic
evidence only. Geant4 fidelity is not established. Zero test events informed any
training, selection or visualization decision in the current gallery.

## Rebuilding

```bash
node exhibition/build_status_update_deck.js \
  exhibition/current/presentations/CBSC_ZDC_status_update_20260805.pptx
python exhibition/build_metrics_catalog.py     # re-hash and re-verify
```

The generator fits every figure to its true aspect ratio by reading the PNG's
own IHDR chunk. The first build hard-coded width and height per image and
stretched seven of eight figures by 10–37%, which is invisible in a file listing
and obvious on a projector.
