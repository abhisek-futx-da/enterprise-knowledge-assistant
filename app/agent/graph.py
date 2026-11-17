"""LangGraph agent: route -> (retrieve -> grade -> generate -> verify) | (MCP tool loop) | direct.

Every loop is bounded (max_attempts rewrites/regenerations, MAX_TOOL_ROUNDS tool calls), so the
worst-case number of LLM calls per question is fixed arithmetic, not open-ended.
"""
import asyncio
import json
import operator
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agent import prompts
from app.agent.llm import ask_json
from app.config import get_settings
from app.db import SessionLocal
from app.retrieval.search import search

MAX_TOOL_ROUNDS = 3
HISTORY_TURNS = 6
_CITATION = re.compile(r"\[(S\d+)\]")

ToolLoader = Callable[[str], Awaitable[list[BaseTool]]]


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict]
    user_id: str
    standalone_question: str
    search_query: str
    route: Literal["retrieve", "tools", "direct"]
    sources: list[dict]
    answer: str
    answer_type: Literal["grounded", "refused", "unverified", "tool", "direct"]
    citations: list[dict]
    grounded: bool | None
    retrievals: int
    generations: int
    feedback: str
    tool_messages: list[BaseMessage]
    tool_calls: Annotated[list[dict], operator.add]
    trace: Annotated[list[str], operator.add]


class RouteDecision(BaseModel):
    route: Literal["retrieve", "tools", "direct"] = "retrieve"
    standalone_question: str = ""


class GradeResult(BaseModel):
    relevant_ids: list[str] = Field(default_factory=list)


class RewriteResult(BaseModel):
    query: str = ""


class VerifyResult(BaseModel):
    grounded: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)


def _llm(config: RunnableConfig) -> BaseChatModel:
    return config["configurable"]["llm"]


def format_sources(sources: list[dict]) -> str:
    def clean(text: str) -> str:  # stop a document from closing its own tag and injecting "instructions"
        return text.replace("</source", "&lt;/source").replace("<source", "&lt;source")

    return "\n\n".join(
        f'<source id="{s["id"]}" file="{clean(s["filename"])}" page="{s["page"]}">\n{clean(s["text"])}\n</source>'
        for s in sources
    )


def _history_text(history: list[dict]) -> str:
    return "\n".join(f'{m["role"]}: {m["content"][:500]}' for m in history[-HISTORY_TURNS:]) or "(none)"


async def route_node(state: AgentState, config: RunnableConfig) -> dict:
    decision = await ask_json(
        _llm(config),
        [SystemMessage(prompts.ROUTER_PROMPT),
         HumanMessage(f"History:\n{_history_text(state.get('history', []))}\n\nMessage: {state['question']}")],
        RouteDecision,
        RouteDecision(),
    )
    standalone = decision.standalone_question.strip() or state["question"]
    return {
        "route": decision.route, "standalone_question": standalone, "search_query": standalone,
        "retrievals": 0, "generations": 0, "trace": [f"route -> {decision.route}"],
    }


async def retrieve_node(state: AgentState, config: RunnableConfig) -> dict:
    s = get_settings()

    def _run() -> list[dict]:
        db = SessionLocal()
        try:
            return [h.to_dict() for h in search(db, state["user_id"], state["search_query"], s.top_k)]
        finally:
            db.close()

    hits = await asyncio.to_thread(_run)
    best = max((h["vector_score"] or 0.0 for h in hits), default=0.0)
    if best < s.min_relevance:  # relevance gate: weak matches are dropped before the LLM can lean on them
        hits = []
    for i, h in enumerate(hits, start=1):
        h["id"] = f"S{i}"
    return {
        "sources": hits, "retrievals": state.get("retrievals", 0) + 1,
        "trace": [f"retrieve '{state['search_query'][:60]}' -> {len(hits)} hits (best cosine {best:.2f})"],
    }


async def grade_node(state: AgentState, config: RunnableConfig) -> dict:
    sources = state.get("sources", [])
    if not sources:
        return {"trace": ["grade -> no sources"]}
    result = await ask_json(
        _llm(config),
        [SystemMessage(prompts.GRADER_PROMPT),
         HumanMessage(f"Question: {state['standalone_question']}\n\n{format_sources(sources)}")],
        GradeResult,
        GradeResult(relevant_ids=[s["id"] for s in sources]),  # grader failure keeps all; verify still gates
    )
    keep = [s for s in sources if s["id"] in set(result.relevant_ids)]
    for i, s in enumerate(keep, start=1):
        s["id"] = f"S{i}"
    return {"sources": keep, "trace": [f"grade -> {len(keep)}/{len(sources)} relevant"]}


def after_grade(state: AgentState) -> str:
    if state.get("sources"):
        return "generate"
    return "rewrite" if state.get("retrievals", 0) < get_settings().max_attempts else "refuse"


async def rewrite_node(state: AgentState, config: RunnableConfig) -> dict:
    result = await ask_json(
        _llm(config),
        [SystemMessage(prompts.REWRITE_PROMPT), HumanMessage(state["standalone_question"])],
        RewriteResult,
        RewriteResult(query=state["standalone_question"]),
    )
    query = result.query.strip() or state["standalone_question"]
    return {"search_query": query, "trace": [f"rewrite -> '{query[:60]}'"]}


async def generate_node(state: AgentState, config: RunnableConfig) -> dict:
    feedback = state.get("feedback")
    user = f"Question: {state['standalone_question']}\n\nSources:\n{format_sources(state['sources'])}"
    if feedback:
        user += f"\n\nYour previous answer was rejected: {feedback}. Answer again using only supported claims."
    reply = await _llm(config).ainvoke([SystemMessage(prompts.ANSWER_PROMPT), HumanMessage(user)])
    return {
        "answer": str(reply.content).strip(), "generations": state.get("generations", 0) + 1,
        "trace": [f"generate (attempt {state.get('generations', 0) + 1})"],
    }


def citations_for(answer: str, sources: list[dict]) -> tuple[list[dict], list[str]]:
    """Code-level citation check: returns (cited sources that exist, ids that were invented)."""
    by_id = {s["id"]: s for s in sources}
    cited = list(dict.fromkeys(_CITATION.findall(answer)))
    valid = [by_id[c] for c in cited if c in by_id]
    invalid = [c for c in cited if c not in by_id]
    return valid, invalid


async def verify_node(state: AgentState, config: RunnableConfig) -> dict:
    answer, sources = state["answer"], state["sources"]
    if prompts.REFUSAL.lower() in answer.lower():
        return {"answer": prompts.REFUSAL, "answer_type": "refused", "grounded": True, "citations": [],
                "trace": ["verify -> model declined (no answer in sources)"]}
    valid, invalid = citations_for(answer, sources)
    if invalid or not valid:
        problem = f"invented citation ids {invalid}" if invalid else "no citations"
        return {"grounded": False, "feedback": problem, "trace": [f"verify -> failed: {problem}"]}
    if get_settings().groundedness_check:
        result = await ask_json(
            _llm(config),
            [SystemMessage(prompts.VERIFY_PROMPT),
             HumanMessage(f"SOURCES:\n{format_sources(valid)}\n\nANSWER:\n{answer}")],
            VerifyResult,
            VerifyResult(grounded=False, unsupported_claims=["verifier reply unreadable"]),
        )
        if not result.grounded:
            problem = "unsupported claims: " + "; ".join(result.unsupported_claims[:3])
            return {"grounded": False, "feedback": problem, "trace": [f"verify -> failed: {problem[:80]}"]}
    citations = [
        {"id": s["id"], "document_id": s["document_id"], "filename": s["filename"],
         "page": s["page"], "chunk_index": s["chunk_index"], "snippet": s["text"]}
        for s in valid
    ]
    return {"grounded": True, "answer_type": "grounded", "citations": citations,
            "trace": [f"verify -> grounded, {len(citations)} citation(s)"]}


def after_verify(state: AgentState) -> str:
    if state.get("grounded"):
        return END
    return "generate" if state.get("generations", 0) < get_settings().max_attempts else "unverified"


async def refuse_node(state: AgentState) -> dict:
    return {"answer": prompts.REFUSAL, "answer_type": "refused", "citations": [], "grounded": True,
            "trace": ["refuse -> nothing relevant in documents"]}


async def unverified_node(state: AgentState) -> dict:
    return {"answer": prompts.UNVERIFIED, "answer_type": "unverified", "citations": [], "grounded": False,
            "trace": ["unverified -> withheld answer that failed verification"]}


async def direct_node(state: AgentState, config: RunnableConfig) -> dict:
    reply = await _llm(config).ainvoke([SystemMessage(prompts.DIRECT_PROMPT), HumanMessage(state["question"])])
    return {"answer": str(reply.content).strip(), "answer_type": "direct", "citations": [], "grounded": None,
            "trace": ["direct reply"]}


async def tool_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """MCP tool loop: discover tools, let the model call them, feed results back. Bounded rounds."""
    loader: ToolLoader = config["configurable"]["tool_loader"]
    try:
        tools = await loader(config["configurable"]["token"])
    except Exception as exc:  # MCP down must degrade to normal RAG, not a 500
        return {"route": "retrieve", "trace": [f"mcp unavailable ({type(exc).__name__}) -> fallback to retrieve"]}
    by_name = {t.name: t for t in tools}
    trace = [f"mcp tools discovered: {sorted(by_name)}"]
    llm = _llm(config).bind_tools(tools)
    messages: list[BaseMessage] = [SystemMessage(prompts.TOOL_AGENT_PROMPT), HumanMessage(state["standalone_question"])]
    calls: list[dict] = []
    for _ in range(MAX_TOOL_ROUNDS):
        reply: AIMessage = await llm.ainvoke(messages)
        messages.append(reply)
        if not reply.tool_calls:
            return {"answer": str(reply.content).strip(), "answer_type": "tool", "citations": [], "grounded": None,
                    "tool_calls": calls, "trace": trace + ["tool agent answered"]}
        for call in reply.tool_calls:
            tool = by_name.get(call["name"])
            if tool is None:
                output = f"Unknown tool '{call['name']}'"
            else:
                try:
                    output = await tool.ainvoke(call["args"])
                except Exception as exc:
                    output = f"Tool error: {exc}"
            output = output if isinstance(output, str) else json.dumps(output, default=str)
            calls.append({"tool": call["name"], "args": call["args"]})
            trace.append(f"tool {call['name']}({json.dumps(call['args'])[:80]})")
            messages.append(ToolMessage(content=output, tool_call_id=call["id"]))
    final = await _llm(config).ainvoke(messages + [HumanMessage("Answer now with the information gathered.")])
    return {"answer": str(final.content).strip(), "answer_type": "tool", "citations": [], "grounded": None,
            "tool_calls": calls, "trace": trace + ["tool round limit reached"]}


def after_route(state: AgentState) -> str:
    return {"retrieve": "retrieve", "tools": "tool_agent", "direct": "direct"}[state["route"]]


def after_tools(state: AgentState) -> str:
    return "retrieve" if state.get("route") == "retrieve" else END


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("route", route_node), ("retrieve", retrieve_node), ("grade", grade_node), ("rewrite", rewrite_node),
        ("generate", generate_node), ("verify", verify_node), ("refuse", refuse_node),
        ("unverified", unverified_node), ("direct", direct_node), ("tool_agent", tool_agent_node),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", after_route, ["retrieve", "tool_agent", "direct"])
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", after_grade, ["generate", "rewrite", "refuse"])
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", after_verify, ["generate", "unverified", END])
    g.add_conditional_edges("tool_agent", after_tools, ["retrieve", END])
    for terminal in ("refuse", "unverified", "direct"):
        g.add_edge(terminal, END)
    return g.compile()


GRAPH = build_graph()


_ACCUMULATED = ("trace", "tool_calls")  # fields with operator.add reducers in AgentState


async def stream_agent(
    *, question: str, history: list[dict], user_id: str, token: str,
    llm: BaseChatModel, tool_loader: ToolLoader,
) -> AsyncIterator[dict[str, Any]]:
    """Yields {"type": "step", ...} as each graph node finishes, then {"type": "final", ...}."""
    config: RunnableConfig = {"configurable": {"llm": llm, "tool_loader": tool_loader, "token": token}}
    state: dict[str, Any] = {"question": question, "history": history, "user_id": user_id}
    async for update in GRAPH.astream(state, config, stream_mode="updates"):
        for node, delta in update.items():
            for key, value in (delta or {}).items():
                state[key] = state.get(key, []) + value if key in _ACCUMULATED else value
            yield {"type": "step", "node": node, "trace": (delta or {}).get("trace", [])}
    yield {"type": "final", **_result(state)}


async def run_agent(**kwargs: Any) -> dict[str, Any]:
    final: dict[str, Any] = {}
    async for event in stream_agent(**kwargs):
        final = event
    final.pop("type")
    return final


def _result(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": state.get("answer", prompts.REFUSAL),
        "answer_type": state.get("answer_type", "refused"),
        "route": state.get("route"),
        "grounded": state.get("grounded"),
        "citations": state.get("citations", []),
        "tool_calls": state.get("tool_calls", []),
        "trace": state.get("trace", []),
    }
