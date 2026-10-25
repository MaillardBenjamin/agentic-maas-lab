.NOTPARALLEL:
.PHONY: bootstrap up seed test demo protocols proofs lab resilience chain-restart security evidence verify stop ai-local ai-openai test-live-local test-live-openai test-access test-bridge-prepare test-bridge-status test-bridge-verify test-partners test-partners-local test-partners-openai test-partners-concurrency test-partners-resilience
bootstrap:
	python3 -c 'from pathlib import Path; p=Path(".env"); p.exists() or (p.write_text(Path(".env.example").read_text()), p.chmod(0o600))'
	docker compose build
up:
	docker compose up -d --wait
	docker compose exec -T api python scripts/wait_ready.py
seed:
	docker compose exec -T api python scripts/seed.py
test:
	docker compose run --rm --no-deps api python -m pytest -q tests
	docker compose run --rm --no-deps web npm test
	docker compose run --rm --no-deps opa test /policies
demo:
	docker compose exec -T api python scripts/smoke.py
protocols:
	docker compose --profile tests up -d agent-fixture
	docker compose exec -T agents python protocol_smoke.py
proofs:
	docker compose --profile proofs run --rm contracts test -vv
	docker compose --profile proofs up -d --wait anvil
	docker compose run --rm --no-deps -v "$(CURDIR)/contracts/proofs:/contracts:ro" api python scripts/deploy_proof.py
	docker compose exec -T api python scripts/reanchor_proofs.py
	docker compose exec -T api python scripts/proof_smoke.py
lab:
	docker compose --profile lab build harness2
	docker compose --profile lab run --rm harness2
resilience:
	docker compose exec -T api python scripts/resilience.py prepare
	@trap 'docker compose start worker' EXIT; \
	docker compose kill -s SIGKILL worker && \
	docker compose exec -T api python scripts/resilience.py signal-stopped && \
	docker compose start worker && \
	docker compose exec -T api python scripts/resilience.py check
security:
	docker compose exec -T api python scripts/security_smoke.py
	@trap 'docker compose start opa' EXIT; \
	docker compose stop opa && \
	docker compose exec -T api python scripts/security_smoke.py opa-down
verify: test demo protocols test-partners test-partners-concurrency test-partners-resilience proofs resilience security lab chain-restart
	docker compose exec -T api python scripts/telemetry_smoke.py
chain-restart:
	docker compose exec -T api python scripts/chain_resilience.py prepare
	docker compose restart anvil
	docker compose --profile proofs up -d --wait anvil
	docker compose exec -T api python scripts/chain_resilience.py check
evidence:
	docker compose ps
	docker compose exec -T api python scripts/evidence.py
stop:
	docker compose stop
ai-local:
	python3 scripts/set_ai_mode.py ollama
	docker compose up -d --no-deps --force-recreate api agents partners
ai-openai:
	python3 scripts/set_ai_mode.py openai
	docker compose up -d --no-deps --force-recreate api agents partners
test-live-local:
	docker compose exec -T api python scripts/live_ai_smoke.py ollama
test-live-openai:
	docker compose exec -T api python scripts/live_ai_smoke.py openai
test-access:
	docker compose exec -T api python scripts/external_access_smoke.py
test-bridge-prepare:
	docker compose exec -T api python scripts/bridge_e2e.py prepare
test-bridge-status:
	docker compose exec -T api python scripts/bridge_e2e.py status
test-bridge-verify:
	docker compose exec -T api python scripts/bridge_e2e.py verify
test-partners:
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose exec -T api python scripts/partner_smoke.py fixture
test-partners-local:
	docker compose exec -T api python scripts/partner_smoke.py ollama
test-partners-openai:
	docker compose exec -T api python scripts/partner_smoke.py openai
test-partners-concurrency:
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose exec -T api python scripts/partner_concurrency.py
test-partners-resilience:
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose exec -T api python scripts/partner_resilience.py prepare
	@trap 'docker compose start worker' EXIT; \
	docker compose stop worker && \
	docker compose exec -T api python scripts/partner_resilience.py queue-stopped && \
	docker compose start worker && \
	docker compose exec -T api python scripts/partner_resilience.py check
