# PreTE-Py

A Python translation of the PreTE optical/IP traffic engineering framework.

This new folder contains a clean, organized Python implementation that follows the same conceptual pipeline as the original Julia project:

- topology provision and topology parsing
- optical/IP cross-layer modeling
- failure scenario generation
- restoration ILP and LP modeling
- TE tunnel generation and traffic engineering evaluation
- availability and throughput metrics

## Structure

- `prete_py/main.py` — command-line entry point
- `prete_py/interface.py` — data reading, topology loading, demand parsing, directory management
- `prete_py/environment.py` — failure scenario generation and connectivity checks
- `prete_py/topoprovision.py` — IP topology provisioning over optical topology
- `prete_py/restoration.py` — restoration routing and ILP/LP models
- `prete_py/simulator.py` — experiment orchestration, optical abstraction, TE, and evaluation
- `prete_py/evaluations.py` — availability and loss metrics
- `prete_py/plotting.py` — plotting helpers
- `prete_py/utils.py` — general utilities

## Installation

```bash
python -m pip install -r requirements.txt
```

## Usage

```bash
python -m prete_py.main --topology B4 --topoindex 1 --traffic 1 --scale 1.0 --te ARROW --parallel ./parallel --cutoff 0.001 --tunnel 2 --scenarioID 1 --ticketsnum 3
```
