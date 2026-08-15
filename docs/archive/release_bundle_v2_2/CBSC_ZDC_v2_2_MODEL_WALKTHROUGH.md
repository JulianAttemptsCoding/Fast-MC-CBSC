# CBSC-ZDC v2.2 Model Walkthrough for an Intro-to-ML Reader

## One-sentence description

The model takes a neutron’s energy and direction, then randomly generates a sparse 6,790-cell calorimeter shower while enforcing exact nonnegative energy accounting and exact hit counts.

## 1. What goes in

Raw input:

```text
[E_total, p_x, p_y, p_z]
```

- `E_total`: neutron total relativistic energy in GeV.
- `p_x,p_y,p_z`: three momentum components in GeV.

Derived values:

```text
K_inc = E_total - m_n
u = p / |p|
```

`K_inc` is the kinetic energy used for the 0–300 GeV training range and 50–250 GeV main result range. `u` is direction.

The network receives five scaled values:

```text
[log(1+K_inc/100), u_x, u_y, u_z, log(E_total)].
```

Logs compress the very wide numerical range so the network does not need to treat 1 GeV and 300 GeV as raw values hundreds of units apart.

## 2. What comes out

Main output:

```text
Y_hat in R_+^6790
```

Each entry is the generated energy for one fixed detector channel. The intended detector has a 400-channel LYSO ECAL followed by a 64-layer steel/scintillator HCAL, with 6,390 HCAL readout channels; the exact cell positions and ganging are read from the frozen production geometry rather than reconstructed from this prose description.

Auxiliary outputs explain how the shower was built:

- visible/no-response indicator;
- total response;
- first positive layer;
- active layers;
- energy in each layer;
- hit count in each layer;
- selected support cells.

These variables are not extra truth available at inference. They are internally generated from the four-vector and random draws.

## 3. Why not generate all 6,790 numbers in one ordinary neural network?

Most cells are exactly zero. A standard dense regression network tends to put a tiny positive number everywhere. It can make average energy loss look good while creating an unphysical cloud of fake hits.

CBSC instead breaks the problem into easier questions:

1. Did the detector respond?
2. How much total energy appeared?
3. Where did the shower begin?
4. Which layers were active?
5. How much energy went to each layer?
6. How many cells were hit in each layer?
7. Which exact cells were hit?
8. How was each layer’s energy divided among those cells?

## 4. The stochastic cascade

### Step A: visible response

The model predicts a probability `p_visible`, then draws a Bernoulli random variable:

```text
V ~ Bernoulli(p_visible).
```

When `V=0`, every output cell is exactly zero.

### Step B: total detector response

For visible events, the model predicts a mixture of probability distributions for total response `T`. A mixture is useful because neutron response can have several regimes rather than one symmetric bell curve.

### Step C: first positive layer and layer activity

A categorical distribution chooses the first positive layer. Bernoulli decisions choose later active layers. Layers before the first positive layer are forced inactive.

### Step D: layer-energy profile

The model uses conditional flow matching. Think of this as learning a velocity field that moves random Gaussian noise into realistic profile shapes.

Training chooses a random time `t` and creates an intermediate point:

```text
x_t = (1-t)x_0 + t x_1,
```

where `x_0` is noise and `x_1` is the true transformed profile. The correct velocity along this straight path is

```text
u_t = x_1 - x_0.
```

The neural network learns to predict this velocity. During generation, numerical integration repeatedly follows the learned velocity from noise to a profile.

A masked softmax converts profile logits into nonnegative shares that sum to one, so

```text
D_l = T q_l,
sum_l D_l = T.
```

No rule says deeper layers must have less energy. Only the total budget is conserved.

### Step E: hit counts

The model predicts a categorical distribution for the number of hit cells in each layer. A categorical distribution can learn arbitrary count shapes; it is not forced to have Poisson mean-variance behavior.

### Step F: geometry-aware support

Every cell is a graph node. Edges connect geometrically related cells. Message passing lets a cell score depend on nearby detector structure. A layer Transformer supplies global longitudinal context.

### Step G: exact support selection

Gumbel-Top-k adds random perturbations to cell scores and selects exactly `K_l` cells without replacement.

This prevents the model from outputting 0.001 GeV in every cell.

### Step H: energy shares and decoder

A second flow predicts relative energy-share logits on selected cells. The decoder normalizes those shares and multiplies by the layer budget.

Raw mode:

```text
Y_i = D_l softmax(r)_i  for selected cells,
Y_i = 0                 otherwise.
```

Therefore:

```text
number of nonzero cells = K_l,
sum of cell energies in layer l = D_l,
sum over all cells = T.
```

## 5. What is beyond the core CBSC hierarchy?

The core CBSC idea is budgeted hierarchical generation: total response → layers → counts → cells.

This implementation adds:

1. a zero-inflated mixture-density response head;
2. conditional flow matching for continuous profile and share distributions;
3. a graph network tied to actual irregular geometry;
4. Transformer layer context;
5. dynamic count-feasibility masks;
6. one stochastic Gumbel-Top-k draw;
7. an exact budget decoder;
8. CLI-enforced provenance, hashes, gates, and checkpoint contracts.

## 6. How training differs from generation

During training, most modules receive the true upstream quantities. This is called teacher forcing. It makes each component learnable and diagnosable.

During final evaluation, the model runs freely using its own generated total, profile, counts, and support. This exposes cascade errors. A good component loss does not guarantee good free-running showers.

## 7. What each loss teaches

- visible BCE: correct zero/nonzero event rate;
- response NLL: distribution of total response;
- first-layer CE: shower-start distribution;
- active BCE: layer occupancy pattern;
- profile flow MSE: continuous longitudinal shape;
- count CE: hit multiplicity;
- support BCE/ranking: which geometry cells should be selected;
- share flow MSE: how selected-cell energy is divided.

The exact decoder enforces conservation; no approximate closure penalty is needed.

## 8. What a successful result means

Success does not mean generated events equal their Geant4 counterparts cell by cell. Geant4 itself is stochastic. Success means the conditional distributions agree: total response, profiles, occupancy, spatial morphology, correlations, diversity, and downstream reconstruction are statistically indistinguishable enough for the declared use case.
