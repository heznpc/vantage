# Run everything through the project's uv env so imports (pyyaml, etc.) resolve.
# Override with `make PYTHON=python3 ...` only if you manage deps yourself.
PYTHON ?= uv run python

.PHONY: all gen-contracts lint test eval validate anticipation clean

# Default: regenerate contracts, lint, run the hard-gate tests.
all: gen-contracts lint test

# SSOT (contracts/*.yaml) -> contracts/generated/ (commit the result; CI diff-gates it)
gen-contracts:
	$(PYTHON) scripts/gen_contracts.py

lint:
	uv run ruff check .

# Hard gates: reproducibility, CSV schema, contract no-drift, anticipation data-path
test:
	$(PYTHON) -m pytest -q

# Report-only ablation (M1 harness): pose-only baseline vs +BEV
eval:
	$(PYTHON) eval/harness.py --backbone rtmo --no-bev --no-calibrated --out eval/out/pose_only.csv
	$(PYTHON) eval/harness.py --backbone rtmo --bev --calibrated --out eval/out/bev.csv

validate:
	$(PYTHON) eval/validate_csv.py eval/out/pose_only.csv
	$(PYTHON) eval/validate_csv.py eval/out/bev.csv

# 3-arm anticipation data-path (synthetic plumbing): generate clips -> metrics + BEV decision
anticipation:
	$(PYTHON) eval/synth.py
	$(PYTHON) eval/validate_manifest.py eval/clips
	$(PYTHON) eval/anticipation.py

clean:
	rm -rf eval/out
