# Production Data and Geometry Contract

## Frozen primary definition

- particle: neutron, PDG 2112;
- event condition: one incident four-vector `[E_total,px,py,pz]` in GeV;
- incident range: `K_inc = E_total-m_n` in `[0,300]` GeV;
- primary result range: `K_inc` in `[50,250]` GeV;
- generator vertex: fixed unless the contract is explicitly expanded;
- target: raw stored calorimeter hit energy summed by channel;
- target units: GeV;
- positions: mm;
- channels: 6,790;
- layers: 65.

Historical detector context to verify, not assume: ECAL is nominally a 20 x 20 LYSO + SiPM plane with 3 x 3 x 7 cm cells and a 60 x 60 cm face; HCAL is nominally a 64-layer steel/scintillator + SiPM sampler in an approximately 65 x 60 x 163 cm envelope. The frozen production geometry artifact is authoritative.

## Required production schema review

The sample YAML is a hypothesis. Verify every branch and unit. The active converter assumes jagged hit arrays per event and constructs one primary neutron from PDG/status arrays.

## Canonical converted shard

Each `.npz` shard contains:

```text
p4_total_gev        float32 [events,4]
kinetic_energy_gev  float32 [events]
event_id            int64   [events]
source_group         int64   [events]
event_ptr            int64   [events+1]
cell_index           int32   [stored_hits]
cell_energy_gev      float32 [stored_hits]
```

`event_ptr[e]:event_ptr[e+1]` selects event `e`’s sparse hits.

## Geometry artifact

`geometry.npz` contains:

```text
cell_id
subdetector
positions_mm
node_features
layer_index
valid_mask
edge_index
edge_features
```

Every dataset manifest records the geometry hash. A checkpoint may be evaluated only with the geometry used to train it.

## Non-negotiable conversion checks

- finite nonnegative hit energy;
- no unknown cell ID;
- fixed vertex within declared tolerance;
- one valid incident neutron;
- mass-shell consistency;
- no silent unit conversion;
- source hashes recorded;
- duplicate channel hits summed, not overwritten;
- intentional 0–300 range filtering separated from malformed-event rejection.

## Split contract

Preferred unit: independent Geant4 run/job/seed family. Current converter maps ROOT file to `source_group`; this is valid only when file boundaries have that meaning. Otherwise use deterministic event hashing and disclose the limitation.

Final-test data may not influence normalization, caps, thresholds, architecture, loss weights, early stopping, or checkpoint choice.
