"""Run in the agents image; checks grounding without inference or network I/O."""
import asyncio
from types import SimpleNamespace
import unittest

from agno.models.response import ModelResponse
from main import ConsultationGuard, model_view


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

    async def test_guard_never_generates_an_execution_tool(self):
        response = await Guard().ainvoke(messages=[SimpleNamespace(role="user", content="Réserve")], tools=[{"function": {"name": "parking_apply"}}])
        self.assertFalse(response.tool_calls)


if __name__ == "__main__":
    unittest.main()
