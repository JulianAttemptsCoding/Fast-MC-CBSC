# QA policy and continuation-handoff verification

Date: 2026-07-28

## Outcome

Active project guidance no longer treats a hardware or scientific QA result as
permission to continue or as a prohibition on a separately specified
experiment. Integrity failures quarantine only their affected artifacts.
Scientific and performance results are preserved as evidence and places for
follow-up QA.

The exact new-chat/new-CLI prompt is:

```text
docs/AGENT_PROMPT_CONTINUE_ANY_BACKEND_20260728.md
SHA-256 071b6d3b69c382aeed519be0b8f9d4726e1b1847a13ab2189748550858662920
27,093 bytes
```

It independently records the model hierarchy, all nine calibrated losses,
6,790-channel/65-layer detector and 107,920-edge graph, ganging contract,
production ROOT and 187-shard prepared-data identities, sparse schema, splits,
current four epoch-4 checkpoints, Vertex procedure, non-Vertex procedure,
repository map, local dashboard, public GitHub Pages site, exhibition, per-epoch
logging, and scientific boundary.

## Organization

- `docs/README.md` is the active documentation index.
- `audit/README.md` explains evidence organization.
- the old Vertex prompt filename is a compatibility pointer.
- obsolete terminal prompts and permission-style Vertex planning files were
  removed.
- path-sensitive audit artifacts were not moved.

Previously frozen July 2026 YAML and their directly coupled manifests were not
hand-edited. They may retain a superseded historical field name. Changing them
would violate the frozen-config contract and break provenance. The field has no
current operational effect.

## Verification

```text
compileall: pass
source pytest: 92 passed, 5 known nonfatal Transformer warnings
public unittest: 7 passed
public TypeScript/Vite build: pass
exhibition: 23 visuals, selected validation position 21
exhibition manifest SHA-256:
262292e4a1b5d0c19f1d21b461f452bdf694b5e09eabc31139e50efd512ec649
git diff --check: pass
cloud jobs submitted: 0
test events opened: 0
```

The first source test invocation omitted `PYTHONPATH=src` and failed during
collection with `ModuleNotFoundError: cbsc_zdc`; no tests or project code ran.
The corrected command set `PYTHONPATH=src` and the complete suite passed.

Scientific state is unchanged: structural and short-horizon optimization
evidence exists for four calibrated epoch-4 families; Geant4 fidelity is not
established.
