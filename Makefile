.NOTPARALLEL:
.PHONY: test-live-audio
test-live-audio:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_live_audio.py
	docker compose run --rm --no-deps web npm test
.PHONY: test-agency
test-agency:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_agency.py
	docker compose run --rm --no-deps web npm test
	docker compose run --rm --no-deps -v "$(CURDIR)/data/agency-evidence:/evidence" api python scripts/agency_smoke.py
.PHONY: test-agent-activity test-agent-activity-local
test-agent-activity:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_agent_activity.py
	docker compose run --rm --no-deps web npm test
test-agent-activity-local:
	docker compose run --rm --no-deps -v "$(CURDIR)/data/activity-evidence:/evidence" api python scripts/agent_activity_smoke.py
.PHONY: perception-assets perception perception-stop test-perception
perception-assets:
	python3 scripts/perception_assets.py
perception: perception-assets
	docker compose --profile perception build perception api web
	docker compose --profile perception up -d --no-deps --wait --wait-timeout 120 perception api web
perception-stop:
	docker compose --profile perception stop perception
test-perception:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_perception.py
	docker compose --profile perception run --rm --no-deps perception python -m pytest -q -p no:cacheprovider /app/test_service.py
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
verify: test demo protocols test-cooperation test-history-routing test-abt test-agency test-budget-concurrency test-partners test-partners-concurrency test-partners-resilience proofs resilience security lab chain-restart
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

.PHONY: test-cooperation test-cooperation-local
test-cooperation:
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts/runtime_guard_test.py:/app/runtime_guard_test.py:ro" agents python runtime_guard_test.py
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/data/cooperation-evidence:/evidence" api python scripts/cooperation_smoke.py fixture
test-cooperation-local:
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/data/cooperation-evidence:/evidence" api python scripts/cooperation_smoke.py ollama

.PHONY: test-parallel-consultations-local
test-parallel-consultations-local:
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/data/cooperation-evidence:/evidence" api python scripts/parallel_consultations_smoke.py

.PHONY: test-history-routing test-history-routing-local
test-history-routing:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_routing.py tests/test_purchase_history.py
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts/runtime_guard_test.py:/app/runtime_guard_test.py:ro" agents python runtime_guard_test.py
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/data/cooperation-evidence:/evidence" api python scripts/history_routing_smoke.py
test-history-routing-local:
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/data/cooperation-evidence:/evidence" api python scripts/history_routing_smoke.py --live

.PHONY: test-abt
test-abt:
	docker compose run --rm --no-deps api python -m pytest -q tests/test_abt.py tests/test_abt_worker.py tests/test_routing.py
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" api python scripts/abt_postgres_test.py

.PHONY: audit-abt test-abt-demo
audit-abt:
	docker compose run --rm --no-deps -v "$(CURDIR)/services/api/maas:/app/maas:ro" -v "$(CURDIR)/tests:/app/tests:ro" -v "$(CURDIR)/scripts:/app/scripts:ro" api python scripts/abt_coverage.py
test-abt-demo:
	docker compose --profile tests up -d agent-fixture partners-fixture
	docker compose exec -T api python scripts/abt_smoke.py

.PHONY: audit-tests test-budget-concurrency
audit-tests:
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" -v "$(CURDIR)/tests:/app/tests:ro" -v "$(CURDIR)/data/test-audit:/evidence" api python scripts/audit_test_coverage.py
test-budget-concurrency:
	docker compose run --rm --no-deps -v "$(CURDIR)/scripts:/app/scripts:ro" api python scripts/budget_postgres_test.py
