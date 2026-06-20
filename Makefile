PYTHON ?= python3
MODEL ?= roneneldan/TinyStories-3M
RESULTS ?= results/00_infrastructure_gate

.PHONY: validate check-env benchmark-train benchmark-sampler estimate mock-report

validate:
	$(PYTHON) scripts/validate_handoff.py

check-env:
	mkdir -p $(RESULTS)
	$(PYTHON) scripts/check_environment.py --model $(MODEL) --output $(RESULTS)/environment.json

benchmark-train:
	mkdir -p $(RESULTS)
	$(PYTHON) scripts/benchmark_train.py --model $(MODEL) --sequence-length 64 --batch-size 32 --warmup-steps 50 --steps 200 --output $(RESULTS)/train_seq64.json
	$(PYTHON) scripts/benchmark_train.py --model $(MODEL) --sequence-length 128 --batch-size 32 --warmup-steps 50 --steps 200 --output $(RESULTS)/train_seq128.json

benchmark-sampler:
	mkdir -p $(RESULTS)
	$(PYTHON) scripts/benchmark_sampler.py --model $(MODEL) --sequence-length 128 --batch-size 32 --num-chains 2 --num-burnin-steps 100 --num-draws 50 --num-steps-between-draws 2 --output $(RESULTS)/sampler_smoke.json

estimate:
	$(PYTHON) scripts/estimate_project.py --train-benchmark $(RESULTS)/train_seq128.json --sampler-benchmark $(RESULTS)/sampler_smoke.json --output-json $(RESULTS)/project_estimate.json --output-md $(RESULTS)/project_estimate.md

mock-report:
	$(PYTHON) reference/mock_report/build_all.py
