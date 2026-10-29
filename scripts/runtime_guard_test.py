"""Run in the agents image; checks grounding and concurrent reads without inference or network I/O."""
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from agno.models.response import ModelResponse
from pydantic import TypeAdapter, ValidationError
from main import ConsultationGuard, model_view
import main as runtime


class Stub:
    async def ainvoke(self, **kwargs):
        return ModelResponse(role="assistant", content="Contacter le parking directement")


class Guard(ConsultationGuard, Stub):
    pass


class RequiredConsultationTests(unittest.IsolatedAsyncioTestCase):
    def test_model_receives_formatted_units_with_no_cent_conversion(self):
        self.assertEqual(model_view({"price_cents": 500, "terms": {"commission_bps": 200}, "available_count": 2}), {"price_eur": "5,00 €", "terms": {"commission_percent": "2,00 %"}, "available_count": 2})
    async def test_sav_cannot_answer_without_consultation(self):
        response = await Guard().ainvoke(messages=[SimpleNamespace(role="user", content="Le parking refuse mon accès")], tools=[{"function": {"name": "consult_organizations"}}])
        call = response.tool_calls[0]["function"]
        self.assertEqual(call["name"], "consult_organizations")
        self.assertIn('"providers": []', call["arguments"])

    async def test_supplier_cannot_answer_without_its_own_data(self):
        response = await Guard().ainvoke(messages=[SimpleNamespace(role="user", content="Quel tarif ?")], tools=[{"function": {"name": "read_provider_context"}}])
        self.assertEqual(response.tool_calls[0]["function"]["name"], "read_provider_context")

    async def test_tool_result_allows_synthesis_without_repeating_reads(self):
        response = await Guard().ainvoke(messages=[SimpleNamespace(role="tool", content="Données sourcées")], tools=[{"function": {"name": "consult_organizations"}}])
        self.assertFalse(response.tool_calls)

    async def test_proof_request_requires_live_verification_not_just_history(self):
        context = runtime.coordination.set({'plan':{'intent':'verification'},'order_id':'selected'})
        trace = runtime.call_trace.set([{'protocol':'MCP','tool':'list_purchases'}])
        try:
            response = await Guard().ainvoke(messages=[SimpleNamespace(role='tool',content='History')], tools=[{'function':{'name':'verify_purchase_proofs'}}])
            self.assertEqual(response.tool_calls[0]['function']['name'], 'verify_purchase_proofs')
            runtime.call_trace.get().append({'protocol':'MCP','tool':'verify_purchase_proofs'})
            response = await Guard().ainvoke(messages=[SimpleNamespace(role='tool',content='Verified')], tools=[{'function':{'name':'verify_purchase_proofs'}}])
            self.assertFalse(response.tool_calls)
        finally:
            runtime.call_trace.reset(trace)
            runtime.coordination.reset(context)

    async def test_abt_request_cannot_be_answered_with_purchase_history_only(self):
        context = runtime.coordination.set({'plan': {'intent': 'account'}})
        trace = runtime.call_trace.set([{'protocol': 'MCP', 'tool': 'list_purchases'}])
        try:
            tools = [{'function': {'name': 'read_abt_account'}}]
            messages = [SimpleNamespace(role='tool', content='Purchase history')]
            response = await Guard().ainvoke(messages=messages, tools=tools)
            self.assertEqual(response.tool_calls[0]['function']['name'], 'read_abt_account')
            runtime.call_trace.get().append({'protocol': 'MCP', 'tool': 'read_abt_account'})
            self.assertFalse((await Guard().ainvoke(messages=messages, tools=tools)).tool_calls)
        finally:
            runtime.call_trace.reset(trace)
            runtime.coordination.reset(context)

    async def test_guard_never_generates_an_execution_tool(self):
        response = await Guard().ainvoke(messages=[SimpleNamespace(role="user", content="Réserve")], tools=[{"function": {"name": "parking_apply"}}])
        self.assertFalse(response.tool_calls)


@contextmanager
def consultation_scope(agent="clearing", providers=None):
    values = {
        runtime.caller: {"id": "lea", "org": "alize", "role": "traveler"},
        runtime.coordination: {"order_id": "selected-order", "providers": providers or ["transport", "bike", "parking"], "plan": {"intent": {"clearing": "clearing", "sav": "sav", "tariffs": "tariff"}[agent], "target": agent, "providers": providers or ["transport", "bike", "parking"], "question": "Demande ciblée"}},
        runtime.current_agent: agent,
        runtime.coordination_token: "signed-session-context",
        runtime.call_trace: [],
        runtime.activity.context: {"run_id": "a" * 32, "agent": agent, "token": "session-token"},
    }
    tokens = [(var, var.set(value)) for var, value in values.items()]
    try:
        yield values[runtime.call_trace]
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class ParallelConsultationTests(unittest.IsolatedAsyncioTestCase):
    async def test_parking_request_with_empty_list_never_calls_other_order_suppliers(self):
        delegate = AsyncMock(return_value="source-parking")
        with consultation_scope("clearing"), patch.object(runtime, "delegate_read", delegate), patch.object(runtime, "read_statement", AsyncMock(return_value='{}')):
            context = runtime.coordination.get()
            context["plan"] = runtime.resolve_plan("Commission parking", context)
            result = json.loads(await runtime.consult_organizations("Commission parking", []))
            self.assertEqual([r["provider"] for r in result["organizations"]], ["parking"])
            delegate.assert_awaited_once_with("parking", "Commission parking", provider=True)

    async def test_unrelated_supplier_is_rejected_before_any_remote_call(self):
        delegate = AsyncMock()
        with consultation_scope("clearing"), patch.object(runtime, "delegate_read", delegate):
            context = runtime.coordination.get()
            context["plan"] = runtime.resolve_plan("Commission parking", context)
            with self.assertRaises(ValueError):
                await runtime.consult_organizations("Commission parking", ["parking", "transport"])
        delegate.assert_not_awaited()

    def test_tool_schema_exposes_canonical_provider_ids(self):
        schema = TypeAdapter(list[runtime.ProviderId]).json_schema()
        self.assertEqual(set(schema["items"]["enum"]), {o["id"] for o in runtime.CATALOG["organizations"]})
        with self.assertRaises(ValidationError):
            TypeAdapter(list[runtime.ProviderId]).validate_python(["Transport", "Vélo", "Parking"])

    async def test_suppliers_and_statement_start_together_with_context_and_order_preserved(self):
        selected = ["transport", "bike", "parking"]
        started, all_started, statement_started = set(), asyncio.Event(), asyncio.Event()
        release = {p: asyncio.Event() for p in selected}
        finished = {p: asyncio.Event() for p in selected}
        async def delegate(aid, question, **kwargs):
            provider = aid
            self.assertEqual(runtime.caller.get()["id"], "lea")
            self.assertEqual(runtime.coordination_token.get(), "signed-session-context")
            self.assertEqual(runtime.activity.context.get()["agent"], "clearing")
            self.assertTrue(kwargs["provider"])
            started.add(provider)
            if len(started) == 3:
                all_started.set()
            await release[provider].wait()
            runtime.call_trace.get().append({"protocol": "A2A", "agent": provider})
            finished[provider].set()
            return "source-" + provider
        async def statement(order_id):
            self.assertEqual(order_id, "selected-order")
            statement_started.set()
            return '{"net_prepaid_eur": "12,00 €"}'
        with consultation_scope() as trace, patch.object(runtime, "delegate_read", delegate), patch.object(runtime, "read_statement", statement):
            task = asyncio.create_task(runtime.consult_organizations("Répartition", selected))
            try:
                await asyncio.wait_for(all_started.wait(), 1)
                await asyncio.wait_for(statement_started.wait(), 1)
                self.assertFalse(task.done())
                for provider in reversed(selected):
                    release[provider].set()
                    await asyncio.wait_for(finished[provider].wait(), 1)
                result = json.loads(await task)
                self.assertEqual([r["provider"] for r in result["organizations"]], selected)
                self.assertEqual(result["global_statement"]["net_prepaid_eur"], "12,00 €")
                self.assertEqual({e["agent"] for e in trace}, set(selected))
            finally:
                for event in release.values():
                    event.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_failure_waits_for_siblings_and_does_not_return_partial_success(self):
        failed, release, finished = asyncio.Event(), asyncio.Event(), set()
        async def delegate(aid, *args, **kwargs):
            provider = aid
            if provider == "transport":
                failed.set()
                raise ValueError("Fournisseur indisponible")
            await release.wait()
            finished.add(provider)
            return "source-" + provider
        with consultation_scope("tariffs") as trace, patch.object(runtime, "delegate_read", delegate):
            task = asyncio.create_task(runtime.consult_organizations("Tarifs", ["transport", "bike", "parking"]))
            try:
                await asyncio.wait_for(failed.wait(), 1)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaisesRegex(ValueError, "Fournisseur indisponible"):
                    await task
                self.assertEqual(finished, {"bike", "parking"})
                self.assertIn({"protocol": "failure"}, trace)
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_entire_provider_selection_is_authorized_before_any_call(self):
        delegate = AsyncMock()
        with consultation_scope("tariffs"), patch.object(runtime, "delegate_read", delegate):
            with self.assertRaises(ValueError):
                await runtime.consult_organizations("Tarifs", ["transport", "unknown"])
        delegate.assert_not_awaited()

    async def test_no_more_than_three_supplier_reads_are_in_flight(self):
        first_batch, release = asyncio.Event(), asyncio.Event()
        active, peak = 0, 0
        async def delegate(aid, *args, **kwargs):
            provider = aid
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 3:
                first_batch.set()
            try:
                await release.wait()
                return provider
            finally:
                active -= 1
        selected = ["supplier" + str(i) for i in range(5)]
        with consultation_scope("tariffs", selected), patch.object(runtime, "organization"), patch.object(runtime, "validate_selection", return_value=selected), patch.object(runtime, "delegate_read", delegate):
            task = asyncio.create_task(runtime.consult_organizations("Tarifs", selected))
            try:
                await asyncio.wait_for(first_batch.wait(), 1)
                self.assertEqual(active, 3)
                release.set()
                result = json.loads(await task)
                self.assertEqual(len(result["organizations"]), 5)
                self.assertEqual(peak, 3)
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_parent_cancellation_drains_every_supplier(self):
        started, active, ready = set(), set(), asyncio.Event()
        async def delegate(aid, *args, **kwargs):
            provider = aid
            active.add(provider)
            started.add(provider)
            if len(started) == 3:
                ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                active.remove(provider)
        with consultation_scope("tariffs"), patch.object(runtime, "delegate_read", delegate):
            task = asyncio.create_task(runtime.consult_organizations("Tarifs", ["transport", "bike", "parking"]))
            try:
                await asyncio.wait_for(ready.wait(), 1)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertFalse(active)

    async def test_sav_policy_is_fetched_alongside_the_supplier(self):
        policy_started = asyncio.Event()
        async def delegate(*args, **kwargs):
            await asyncio.wait_for(policy_started.wait(), 1)
            return "source-parking"
        async def policy(question):
            policy_started.set()
            return '{"sources": [{"id": "sav-1"}]}'
        with consultation_scope("sav"), patch.object(runtime, "delegate_read", delegate), patch.object(runtime, "search_tariffs", policy):
            result = json.loads(await runtime.consult_organizations("Règle SAV", ["parking"]))
            self.assertEqual(result["maas_policy"]["sources"][0]["id"], "sav-1")


if __name__ == "__main__":
    unittest.main()
