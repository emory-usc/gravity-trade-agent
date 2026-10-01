"""LangGraph agent.

Two nodes:

1. ``scan`` — runs the deterministic six-layer pipeline via the tools and
   stores a structured SignalBundle in state.
2. ``thesis`` — turns the bundle into a TradeThesis. With an LLM configured it
   writes the narrative from the evidence; without one it falls back to the
   deterministic generator, so the graph runs end-to-end offline.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from gravity_trade.config import get_settings
from gravity_trade.data import load_sample_data
from gravity_trade.models import SignalBundle, TradeThesis
from gravity_trade.scoring import compute_bundle
from gravity_trade.thesis import generate_offline_thesis


class AgentState(TypedDict):
    ticker: str
    bundle: SignalBundle
    thesis: TradeThesis
    generated_by: str


def _scan_node(state: AgentState) -> dict[str, Any]:
    data = load_sample_data(state["ticker"])
    bundle = compute_bundle(state["ticker"], data)
    return {"bundle": bundle}


def _thesis_node(state: AgentState) -> dict[str, Any]:
    settings = get_settings()
    bundle: SignalBundle = state["bundle"]

    if settings.llm_configured:
        thesis = _llm_thesis(bundle, settings)
    else:
        thesis = generate_offline_thesis(bundle)

    return {"thesis": thesis, "generated_by": thesis.generated_by}


def _llm_thesis(bundle: SignalBundle, settings: Any) -> TradeThesis:
    """Generate the thesis with a tool-calling LLM, constrained to the schema."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.2,
    ).with_structured_output(TradeThesis)

    prompt = (
        "You are a disciplined directional equities analyst using the Gravity Trade "
        "six-layer framework (max pain, beta, GEX, dark pool, sector, term structure).\n\n"
        "Here is the computed signal bundle (authoritative — do not invent new numbers):\n"
        f"{bundle.model_dump_json(indent=2)}\n\n"
        "Produce a TradeThesis. Preserve ticker, direction, conviction, and high_conviction "
        "exactly as given. Write the thesis citing the layer evidence, an entry plan "
        "(Monday), an exit plan (Friday 2pm CT), and risk notes."
    )
    return llm.invoke(prompt)


def build_agent() -> Any:
    """Build the compiled LangGraph agent."""
    graph = StateGraph(AgentState)
    graph.add_node("scan", _scan_node)
    graph.add_node("thesis", _thesis_node)
    graph.set_entry_point("scan")
    graph.add_edge("scan", "thesis")
    graph.add_edge("thesis", END)
    return graph.compile()


def run_agent(ticker: str) -> TradeThesis:
    """Convenience: run the compiled agent for a ticker and return the thesis."""
    app = build_agent()
    result = app.invoke({"ticker": ticker.upper()})
    return result["thesis"]
