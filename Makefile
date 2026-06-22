.PHONY: all gen-contracts lint test eval validate anticipation clean

# Default: regenerate contracts, lint, run the hard-gate tests.
all: gen-contracts lint test

# SSOT (contracts/*.yaml) -> contracts/generated/ (commit the result; CI diff-gates it)
gen-contracts:
	python3 scripts/gen_contracts.py

lint:
	uv run ruff check . || ruff check .

# Hard gates: reproducibility, CSV schema, contract no-drift (stdlib; no install needed)
test:
	python3 tests/test_reproducibility.py
	python3 tests/test_csv_schema.py
	python3 tests/test_contracts_no_drift.py

# Report-only ablation: pose-only baseline vs +BEV treatment
eval:
	python3 eval/harness.py --backbone rtmo --no-bev --no-calibrated --out eval/out/pose_only.csv
	python3 eval/harness.py --backbone rtmo --bev --calibrated --out eval/out/bev.csv

validate:
	python3 eval/validate_csv.py eval/out/pose_only.csv
	python3 eval/validate_csv.py eval/out/bev.csv

# 3-arm anticipation data-path (synthetic plumbing): generate clips -> metrics + BEV decision
anticipation:
	python3 eval/synth.py
	python3 eval/anticipation.py

clean:
	rm -rf eval/out
