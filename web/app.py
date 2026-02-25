"""Soco Marketing CLI — 3-Pane Agentic FastHTML Web UI."""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from starlette.responses import StreamingResponse, FileResponse

# Ensure project root is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fasthtml.common import *

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from pydantic import Field, create_model

from agents.base import ToolStatus
from agents.registry import AgentRegistry
from context.session import SessionContext

# ── Boot ─────────────────────────────────────────────────────────────────

def boot():
    from integrations.xai_int import XaiIntegration
    from integrations.arcade_int import ArcadeIntegration
    from integrations.playwright_int import PlaywrightIntegration
    from integrations.composio_int import ComposioIntegration
    from agents.content import ContentAgent
    from agents.strategy import StrategyAgent
    from agents.social import SocialAgent
    from agents.cro import CroAgent
    from agents.seo import SeoAgent
    from agents.ads import AdsAgent

    AgentRegistry.reset()
    reg = AgentRegistry.get()
    session_ctx = SessionContext()

    for Int in [XaiIntegration, ArcadeIntegration, PlaywrightIntegration, ComposioIntegration]:
        inst = Int()
        if inst.is_configured():
            session_ctx.set_integration(inst.name, inst)

    for Cls in [ContentAgent, StrategyAgent, SocialAgent, CroAgent, SeoAgent, AdsAgent]:
        reg.register(Cls())

    return reg, session_ctx

registry, soco_ctx = boot()

# ── LangGraph Agent ──────────────────────────────────────────────────────

def build_langchain_tools(reg: AgentRegistry, ctx: SessionContext) -> list[StructuredTool]:
    """Convert every soco ToolDefinition into a LangChain StructuredTool."""
    tools = []
    for agent_name, tool_def in reg.all_tool_definitions():
        # Build Pydantic args schema from tool_def.parameters
        fields = {}
        for param_name, param_info in tool_def.parameters.items():
            desc = param_info.get("description", param_name)
            default = param_info.get("default", "")
            if param_info.get("required"):
                fields[param_name] = (str, Field(description=desc))
            else:
                fields[param_name] = (str, Field(default=default or "", description=desc))

        # If no parameters, create a model with no fields
        schema_model = create_model(
            f"{agent_name}_{tool_def.name}_args", **fields
        ) if fields else create_model(f"{agent_name}_{tool_def.name}_args")

        # Capture agent_name and tool_name in closure
        def _make_fn(a_name: str, t_name: str):
            async def _run(**kwargs: str) -> str:
                agent_obj = reg.get_agent(a_name)
                if not agent_obj:
                    return f"Error: agent '{a_name}' not found"
                result = await agent_obj.execute(t_name, kwargs, ctx)
                if result.status == ToolStatus.SUCCESS:
                    return result.output
                return result.error or result.follow_up_prompt or result.output or "Tool returned no output"
            return _run

        lc_tool = StructuredTool.from_function(
            coroutine=_make_fn(agent_name, tool_def.name),
            name=f"{agent_name}__{tool_def.name}",
            description=tool_def.long_help or tool_def.description,
            args_schema=schema_model,
        )
        tools.append(lc_tool)
    return tools


SYSTEM_PROMPT_TEMPLATE = """You are Soco, an AI marketing assistant. You help users with marketing tasks using specialized tools.

Today's date is {today}. IMPORTANT: All content you generate must be current and relevant.
Reference recent trends, data, and events from {current_year}. Never cite outdated years or stale statistics.

If the user's request maps to a tool, use the tool. For conversational messages (greetings, questions about capabilities), respond directly.
Always be helpful, concise, and action-oriented. Present tool results clearly without mentioning the tool mechanism.

Product context: {product_context}"""


def build_agent(reg: AgentRegistry, ctx: SessionContext):
    """Build a LangGraph ReAct agent with soco tools."""
    xai = ctx.get_integration("xai")
    if not xai:
        return None

    llm = ChatOpenAI(
        api_key=xai.api_key,
        base_url="https://api.x.ai/v1",
        model=xai.model,
        temperature=0.5,
        max_tokens=3000,
    )
    tools = build_langchain_tools(reg, ctx)

    from datetime import date
    today = date.today()
    product_block = ctx.product.to_prompt_block() or "Not set"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        today=today, current_year=today.year, product_context=product_block,
    )

    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)


async def agent_chat_stream(user_msg: str, history: list, session_list: list):
    """Stream SSE events from the LangGraph ReAct agent. Appends final reply to session_list."""
    graph = build_agent(registry, soco_ctx)
    if graph is None:
        yield f"event: token\ndata: {json.dumps({'text': 'XAI integration not configured. Set XAI_API_KEY in .env'})}\n\n"
        session_list.append({"role": "assistant", "content": "XAI integration not configured."})
        yield f"event: done\ndata: {json.dumps({'tool_count': 0})}\n\n"
        return

    messages = []
    for h in history[-20:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_msg))

    tool_count = 0
    accumulated_text = []

    try:
        async for event in graph.astream_events({"messages": messages}, version="v2"):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                    if not getattr(chunk, "tool_call_chunks", None):
                        accumulated_text.append(chunk.content)
                        yield f"event: token\ndata: {json.dumps({'text': chunk.content})}\n\n"

            elif kind == "on_tool_start":
                tool_count += 1
                name = event.get("name", "unknown")
                cmd = name.replace("__", ":", 1)
                args = event["data"].get("input", {})
                # Look up estimated time from registry
                eta = _get_tool_eta(cmd)
                yield f"event: tool_start\ndata: {json.dumps({'command': cmd, 'args': args, 'eta': eta})}\n\n"
                accumulated_text.clear()

            elif kind == "on_tool_end":
                name = event.get("name", "unknown")
                cmd = name.replace("__", ":", 1)
                output_raw = event["data"].get("output", "")
                if hasattr(output_raw, "content"):
                    output_str = output_raw.content
                elif isinstance(output_raw, str):
                    output_str = output_raw
                else:
                    output_str = str(output_raw)
                status = "error" if (hasattr(output_raw, "status") and output_raw.status == "error") else "success"
                yield f"event: tool_end\ndata: {json.dumps({'command': cmd, 'status': status, 'output': output_str[:2000]})}\n\n"

    except Exception as e:
        err_msg = f"Error: {e}"
        accumulated_text.append(err_msg)
        yield f"event: token\ndata: {json.dumps({'text': err_msg})}\n\n"

    final_reply = "".join(accumulated_text) or "I processed your request but have no additional commentary."
    session_list.append({"role": "assistant", "content": final_reply})
    yield f"event: done\ndata: {json.dumps({'tool_count': tool_count})}\n\n"


# ── In-memory chat store ─────────────────────────────────────────────────

chat_sessions: dict[str, list] = {}           # session_id -> [{role, content}]
user_chats: dict[str, list[str]] = {}         # user_id (cookie) -> [sid, ...] newest first
shared_chats: dict[str, str] = {}             # share_id -> session_id

STATIC_DIR = Path(__file__).parent / "static"

# ── CSS ──────────────────────────────────────────────────────────────────

css = Style("""
:root {
    --bg: #f9fafb; --surface: #ffffff; --surface2: #f3f4f6;
    --border: #e5e7eb; --text: #111827; --muted: #6b7280;
    --accent: #2563eb; --accent2: #7c3aed; --green: #16a34a;
    --red: #dc2626; --yellow: #d97706;
    --gradient: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-top: env(safe-area-inset-top, 0px);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg); color: var(--text); overflow: hidden; line-height: 1.5;
}

/* ── 3-Pane Layout ─────────────────────────────────────────────── */
.app {
    display: grid;
    grid-template-columns: 260px 1fr;
    height: 100vh; overflow: hidden;
    padding-right: 400px; transition: padding-right .3s ease;
}
.app.pane-closed { padding-right: 0; }

/* ── Left Pane: Tools Reference ────────────────────────────────── */
.left-pane {
    background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
    z-index: 200;
}
.left-header {
    padding: 1rem 1.25rem; border-bottom: 1px solid var(--surface2);
    display: flex; align-items: center; justify-content: space-between;
}
.left-header h1 { font-size: 1rem; font-weight: 700; }
.left-header h1 span {
    background: var(--gradient); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; background-clip: text;
}
.left-header .badge {
    font-size: .65rem; color: var(--accent2); background: #f5f3ff;
    padding: .15rem .5rem; border-radius: 4px; font-weight: 600;
    letter-spacing: .3px;
}
.left-body { flex: 1; overflow-y: auto; padding: .75rem; }

/* Integration indicators */
.int-row { display: flex; gap: .5rem; padding: .5rem; flex-wrap: wrap; }
.int-dot {
    font-size: .7rem; padding: .15rem .45rem; border-radius: 9999px;
    border: 1px solid var(--border);
}
.int-dot.on { color: var(--green); border-color: var(--green); }
.int-dot.off { color: var(--muted); }

/* Agent groups */
.agent-group { margin-bottom: .25rem; }
.agent-toggle {
    width: 100%; text-align: left; background: none; border: none;
    color: var(--text); padding: .5rem .6rem; cursor: pointer;
    font-size: .8rem; font-weight: 600; display: flex;
    align-items: center; justify-content: space-between;
    border-radius: .5rem; transition: background .15s;
}
.agent-toggle:hover { background: var(--surface2); }
.agent-toggle .arrow { color: var(--muted); font-size: .65rem; transition: transform .2s; }
.agent-toggle.open .arrow { transform: rotate(90deg); }
.agent-toggle .cnt { color: var(--muted); font-weight: 400; font-size: .7rem; }
.tool-list { display: none; padding: 0 .25rem .25rem .75rem; }
.tool-list.open { display: block; }
.tool-item {
    display: block; width: 100%; text-align: left;
    background: none; border: none; color: var(--muted);
    padding: .3rem .5rem; cursor: pointer; font-size: .75rem;
    border-radius: .3rem; transition: all .15s;
    font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
}
.tool-item:hover { background: #eff6ff; color: var(--accent); }

/* Product context in sidebar */
.ctx-sidebar {
    border-top: 1px solid var(--surface2); padding: .75rem;
}
.ctx-sidebar h4 {
    font-size: .75rem; color: var(--muted); font-weight: 500;
    margin-bottom: .5rem;
}
.ctx-mini-field {
    display: flex; gap: .35rem; margin-bottom: .35rem; font-size: .7rem;
}
.ctx-mini-field label { min-width: 60px; color: var(--muted); }
.ctx-mini-field input {
    flex: 1; background: var(--bg); border: 1px solid var(--border);
    border-radius: .35rem; padding: .2rem .4rem; color: var(--text);
    outline: none; font-size: .7rem;
}
.ctx-mini-field input:focus { border-color: var(--accent); }
.ctx-save {
    width: 100%; background: var(--gradient); color: #fff; border: none;
    border-radius: .5rem; padding: .35rem; cursor: pointer;
    font-size: .7rem; font-weight: 600; margin-top: .35rem;
    transition: opacity .15s;
}
.ctx-save:hover { opacity: .9; }

/* ── Chat History (left pane) ──────────────────────────────────── */
.chat-history { padding: .5rem .75rem; border-bottom: 1px solid var(--surface2); }
.chat-history-label {
    font-size: .65rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: .05em; color: var(--muted); margin-bottom: .35rem;
}
.chat-new-btn {
    width: 100%; padding: .4rem .6rem; background: var(--gradient);
    color: #fff; border: none; border-radius: .5rem; font-size: .75rem;
    font-weight: 600; cursor: pointer; margin-bottom: .5rem;
    transition: opacity .15s; min-height: 2rem;
}
.chat-new-btn:hover { opacity: .9; }
.chat-history-item {
    display: flex; align-items: center; gap: .4rem;
    width: 100%; text-align: left; background: none; border: none;
    color: var(--muted); padding: .35rem .5rem; cursor: pointer;
    font-size: .75rem; border-radius: .4rem; transition: all .15s;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chat-history-item:hover { background: var(--surface2); color: var(--text); }
.chat-history-item.active { background: #eff6ff; color: var(--accent); font-weight: 600; }
.chat-history-item .chat-dot {
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
    background: var(--border);
}
.chat-history-item.active .chat-dot { background: var(--accent); }

/* ── Center Pane: Chat ─────────────────────────────────────────── */
.center-pane {
    display: flex; flex-direction: column; overflow: hidden;
    position: relative; background: var(--bg);
}
.chat-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: .65rem 1.25rem; background: var(--surface);
    border-bottom: 1px solid var(--border); min-height: 2.75rem;
    position: relative; z-index: 101; gap: .5rem;
}
.chat-header-left { display: flex; align-items: center; gap: .5rem; }
.chat-header-title { font-size: .9rem; font-weight: 600; color: var(--text); }
.chat-header-actions { display: flex; gap: .5rem; align-items: center; }
.think-badge {
    background: var(--gradient); color: #fff; border-radius: 50%;
    width: 1.1rem; height: 1.1rem; display: inline-flex;
    align-items: center; justify-content: center;
    font-size: .6rem; font-weight: 700;
}
.think-btn {
    padding: .35rem .7rem; background: transparent;
    border: 1px solid var(--border); border-radius: .5rem;
    color: var(--muted); font-size: .75rem; cursor: pointer;
    transition: all .15s; display: flex; align-items: center; gap: .3rem;
}
.think-btn:hover { border-color: #93c5fd; color: var(--accent); background: #eff6ff; }
.think-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* Share button */
.share-btn {
    padding: .35rem .55rem; background: transparent;
    border: 1px solid var(--border); border-radius: .5rem;
    color: var(--muted); font-size: .85rem; cursor: pointer;
    transition: all .15s; display: flex; align-items: center;
    line-height: 1;
}
.share-btn:hover { border-color: #93c5fd; color: var(--accent); background: #eff6ff; }

/* Mobile menu button */
.mobile-menu-btn {
    display: none; padding: .35rem .5rem; background: transparent;
    border: 1px solid var(--border); border-radius: .5rem;
    color: var(--text); font-size: 1.1rem; cursor: pointer;
    line-height: 1; transition: all .15s;
}
.mobile-menu-btn:hover { background: var(--surface2); }

/* Left pane overlay backdrop */
.left-overlay {
    display: none; position: fixed; inset: 0; z-index: 199;
    background: rgba(0,0,0,.4); backdrop-filter: blur(2px);
}
.left-overlay.visible { display: block; }

/* Share toast */
.share-toast {
    position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(100px);
    background: var(--text); color: #fff; padding: .6rem 1.25rem;
    border-radius: .75rem; font-size: .85rem; font-weight: 500;
    z-index: 9999; opacity: 0; transition: all .3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,.15);
}
.share-toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }

/* Messages area */
.messages {
    flex: 1; overflow-y: auto; padding: 1.25rem;
    display: flex; flex-direction: column; gap: .75rem;
}
.messages:empty::before {
    content: "Ask me anything about marketing \\2014  I'll pick the right tool and get it done.";
    color: var(--muted); text-align: center; padding: 4rem 2rem;
    font-size: .9rem; font-style: italic;
}
.msg { display: flex; flex-direction: column; max-width: 85%; animation: msgIn .25s ease; }
@keyframes msgIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.msg-user { align-self: flex-end; }
.msg-assistant { align-self: flex-start; }
.msg-bubble {
    padding: .65rem 1rem; border-radius: 1rem;
    font-size: .85rem; line-height: 1.7; word-break: break-word;
}
.msg-user .msg-bubble {
    background: var(--gradient); color: #fff;
    border-bottom-right-radius: .3rem;
}
.msg-assistant .msg-bubble {
    background: var(--surface); border: 1px solid var(--border);
    border-bottom-left-radius: .3rem;
    white-space: pre-wrap; color: var(--text);
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}

/* Tool call badges in chat */
.tool-badge {
    display: inline-flex; align-items: center; gap: .3rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: .5rem; padding: .25rem .6rem; font-size: .7rem;
    font-family: 'SF Mono', 'Fira Code', Consolas, monospace; margin: .35rem 0;
    cursor: pointer; transition: all .15s;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.tool-badge:hover { border-color: #93c5fd; background: #eff6ff; }
.tool-badge .dot {
    width: 6px; height: 6px; border-radius: 50%;
}
.tool-badge .dot.success { background: var(--green); }
.tool-badge .dot.error { background: var(--red); }

/* Streaming indicator */
.streaming::after {
    content: '\\25CA'; animation: blink 1s infinite; opacity: .7; margin-left: 2px;
}
@keyframes blink { 0%,50% { opacity: .7; } 51%,100% { opacity: 0; } }

/* Chat input */
.chat-form {
    display: flex; align-items: flex-end; gap: .5rem;
    padding: .75rem 1.25rem; background: var(--surface);
    border-top: 1px solid var(--border);
    padding-bottom: calc(.75rem + var(--safe-bottom));
}
.chat-textarea {
    flex: 1; min-width: 0; width: 100%;
    padding: .65rem 1rem; border: 1.5px solid var(--border);
    border-radius: .75rem; background: var(--bg);
    color: var(--text); font-family: inherit; font-size: .9rem; line-height: 1.5;
    resize: none; min-height: 2.75rem; max-height: 8rem;
    overflow-y: hidden; outline: none; transition: border-color .2s;
}
.chat-textarea:focus { border-color: #93c5fd; }
.chat-send {
    padding: .65rem 1.25rem; background: var(--gradient); color: #fff;
    border: none; border-radius: .75rem; font-weight: 600; font-size: .85rem;
    cursor: pointer; transition: opacity .15s, transform .15s; min-height: 2.75rem;
    flex-shrink: 0;
}
.chat-send:hover { opacity: .9; transform: scale(1.03); }
.chat-send:disabled { opacity: .35; cursor: not-allowed; transform: none; }

/* Suggestions */
.suggestions { display: flex; flex-wrap: wrap; gap: .5rem; padding: .5rem 1.25rem; }
.suggest-btn {
    padding: .35rem .75rem; background: var(--surface);
    border: 1px solid var(--border); border-radius: 1.25rem;
    color: var(--muted); font-size: .75rem; cursor: pointer;
    transition: all .18s; font-weight: 500;
}
.suggest-btn:hover {
    background: #eff6ff; border-color: #93c5fd;
    color: var(--accent); transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(37,99,235,.1);
}

/* ── Right Pane: Thinking Trace ────────────────────────────────── */
.right-pane {
    position: fixed; top: 0; right: -420px; width: 400px; height: 100vh;
    background: var(--surface); border-left: 1px solid var(--border);
    box-shadow: -4px 0 24px rgba(0,0,0,.08); z-index: 100;
    display: flex; flex-direction: column; transition: right .3s ease;
}
.right-pane.open { right: 0; }
.right-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: .85rem 1.25rem; border-bottom: 1px solid var(--border);
}
.right-header h3 { font-size: .9rem; font-weight: 600; color: var(--text); }
.right-close {
    background: none; border: none; color: var(--muted); font-size: 1.1rem;
    cursor: pointer; padding: .2rem; border-radius: .25rem;
}
.right-close:hover { color: var(--text); background: var(--surface2); }
.right-body { flex: 1; overflow-y: auto; padding: 1rem; }

/* Thinking steps */
.think-step {
    padding: .65rem; margin-bottom: .65rem; background: var(--bg);
    border-radius: .5rem; border-left: 3px solid var(--accent);
    animation: msgIn .2s ease;
}
.think-step.tool-call { border-left-color: var(--yellow); }
.think-step.error { border-left-color: var(--red); }
.think-step-type {
    font-weight: 600; font-size: .7rem; text-transform: uppercase;
    letter-spacing: .03em; margin-bottom: .25rem; color: var(--accent);
}
.think-step.tool-call .think-step-type { color: var(--yellow); }
.think-step.error .think-step-type { color: var(--red); }
.think-step-body {
    font-size: .78rem; line-height: 1.6; color: var(--text);
    white-space: pre-wrap; word-break: break-word;
    max-height: 200px; overflow-y: auto;
}

/* ── Share View ────────────────────────────────────────────────── */
.share-page {
    max-width: 720px; margin: 0 auto; min-height: 100vh;
    display: flex; flex-direction: column;
}
.share-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1rem 1.25rem; background: var(--surface);
    border-bottom: 1px solid var(--border); gap: .5rem;
}
.share-header-title {
    font-size: .9rem; font-weight: 600; color: var(--text);
    display: flex; align-items: center; gap: .5rem;
}
.share-header-actions { display: flex; gap: .5rem; }
.share-link-btn {
    padding: .4rem .8rem; background: var(--gradient); color: #fff;
    border: none; border-radius: .5rem; font-size: .75rem;
    font-weight: 600; cursor: pointer; text-decoration: none;
    transition: opacity .15s;
}
.share-link-btn:hover { opacity: .9; }
.share-copy-btn {
    padding: .4rem .8rem; background: transparent; color: var(--muted);
    border: 1px solid var(--border); border-radius: .5rem;
    font-size: .75rem; cursor: pointer; transition: all .15s;
}
.share-copy-btn:hover { border-color: #93c5fd; color: var(--accent); }
.share-messages {
    flex: 1; overflow-y: auto; padding: 1.25rem;
    display: flex; flex-direction: column; gap: .75rem;
}

/* Transition only after first paint (prevents slide-out flash on load) */
.left-pane.animated { transition: left .3s ease; }

/* ── Responsive: Mobile (<768px) ───────────────────────────────── */
@media (max-width: 767px) {
    .app {
        grid-template-columns: 1fr; padding-right: 0 !important;
    }
    .left-pane {
        position: fixed; top: 0; left: -280px; width: 280px; height: 100vh;
        box-shadow: 4px 0 24px rgba(0,0,0,.1);
    }
    .left-pane.open { left: 0; }
    .right-pane { display: none !important; }
    .chat-header-actions .think-btn,
    .chat-header-actions .think-badge { display: none; }
    .mobile-menu-btn { display: flex; }
    .chat-send, .suggest-btn, .chat-new-btn,
    .share-btn, .tool-item, .agent-toggle { min-height: 44px; }
    .suggestions {
        flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch;
        scrollbar-width: none; padding-bottom: .75rem;
    }
    .suggestions::-webkit-scrollbar { display: none; }
    .suggest-btn { white-space: nowrap; flex-shrink: 0; }
    .msg { max-width: 92%; }
    .chat-form { padding: .5rem .75rem; padding-bottom: calc(.5rem + var(--safe-bottom)); }
    .chat-header { padding: .5rem .75rem; }
    .messages { padding: .75rem; }
}

/* ── Responsive: Tablet (768px–1024px) ─────────────────────────── */
@media (min-width: 768px) and (max-width: 1024px) {
    .app {
        grid-template-columns: 1fr; padding-right: 0 !important;
    }
    .left-pane {
        position: fixed; top: 0; left: -280px; width: 280px; height: 100vh;
        box-shadow: 4px 0 24px rgba(0,0,0,.1);
    }
    .left-pane.open { left: 0; }
    .right-pane { width: 380px; right: -400px; }
    .right-pane.open { right: 0; }
    .app:not(.pane-closed) { padding-right: 380px; }
    .mobile-menu-btn { display: flex; }
}

/* ── Responsive: Desktop (>1024px) ─────────────────────────────── */
@media (min-width: 1025px) {
    .left-pane { position: static !important; left: auto !important; }
}
""")

fonts = (
    Link(rel="preconnect", href="https://fonts.googleapis.com"),
    Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
)

pwa_meta = (
    Meta(name="theme-color", content="#2563eb"),
    Meta(name="apple-mobile-web-app-capable", content="yes"),
    Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
    Link(rel="manifest", href="/manifest.json"),
    Link(rel="icon", href="/icon.svg", type="image/svg+xml"),
)

app, rt = fast_app(
    pico=False,
    hdrs=[css, *fonts, *pwa_meta, Script(src="https://unpkg.com/htmx.org@2.0.4")],
    secret_key=os.getenv("SESSION_SECRET", "soco-dev-key-change-me"),
)

# ── Helpers ───────────────────────────────────────────────────────────────

def _get_tool_eta(cmd: str) -> int:
    """Look up estimated_seconds for an agent:tool command string."""
    parts = cmd.split(":", 1)
    if len(parts) == 2:
        agent = registry.get_agent(parts[0])
        if agent:
            tool_def = agent.resolve_tool(parts[1])
            if tool_def:
                return tool_def.estimated_seconds
    return 10


def _get_chat_title(sid: str) -> str:
    """First user message truncated to ~35 chars, or fallback."""
    msgs = chat_sessions.get(sid, [])
    for m in msgs:
        if m["role"] == "user":
            text = m["content"]
            return text[:35] + ("..." if len(text) > 35 else "")
    return "New chat"


def _ensure_user(sess) -> str:
    """Return user_id cookie, creating one if needed."""
    if "uid" not in sess:
        sess["uid"] = str(uuid.uuid4())
    return sess["uid"]


def _ensure_session(sess) -> str:
    """Return current session id, creating one if needed. Links to user."""
    uid = _ensure_user(sess)
    if "sid" not in sess:
        sess["sid"] = str(uuid.uuid4())
    sid = sess["sid"]
    if sid not in chat_sessions:
        chat_sessions[sid] = []
    if uid not in user_chats:
        user_chats[uid] = []
    if sid not in user_chats[uid]:
        user_chats[uid].insert(0, sid)
    return sid

# ── Components ───────────────────────────────────────────────────────────

def chat_history_section(uid: str, current_sid: str):
    """Render chat history list for the left pane."""
    sids = user_chats.get(uid, [])
    items = []
    for sid in sids[:20]:
        title = _get_chat_title(sid)
        is_active = sid == current_sid
        items.append(
            Button(
                Span(cls="chat-dot"),
                Span(title),
                cls=f"chat-history-item{'  active' if is_active else ''}",
                onclick=f"loadChat('{sid}')",
            )
        )

    return Div(
        Button("+ New Chat", cls="chat-new-btn", onclick="newChat()"),
        Div("Chats", cls="chat-history-label") if items else "",
        *items,
        cls="chat-history",
    )


def left_pane(uid: str = "", current_sid: str = ""):
    agents = registry.all_agents()
    total = sum(len(a.get_tools()) for a in agents)

    # Integration dots
    int_dots = Div(
        *[Span(n, cls=f"int-dot {'on' if soco_ctx.get_integration(n) else 'off'}")
          for n in ["xai", "arcade", "playwright", "composio"]],
        cls="int-row",
    )

    # Agent groups with collapsible tool lists
    groups = []
    for agent in agents:
        tools = agent.get_tools()
        agent_id = f"ag-{agent.name}"
        tool_items = [
            Button(
                f"{agent.name}:{t.name}",
                cls="tool-item",
                onclick=f"fillChat('{agent.name}:{t.name}')",
                title=t.description,
            )
            for t in tools
        ]
        groups.append(Div(
            Button(
                Span(agent.name),
                Span(f"{len(tools)}", cls="cnt"),
                Span(">", cls="arrow"),
                cls="agent-toggle",
                onclick=f"toggleGroup('{agent_id}')",
                id=f"btn-{agent_id}",
            ),
            Div(*tool_items, cls="tool-list", id=agent_id),
            cls="agent-group",
        ))

    # Context form
    p = soco_ctx.product
    ctx_fields = [("company", p.company), ("product", p.product),
                  ("audience", p.audience), ("tone", p.tone)]
    ctx_form = Form(
        H4("Product Context"),
        *[Div(
            Label(k.title()), Input(name=k, value=v, placeholder=k),
            cls="ctx-mini-field",
        ) for k, v in ctx_fields],
        Button("Save", cls="ctx-save", type="submit"),
        cls="ctx-sidebar",
        hx_post="/context",
        hx_target="#ctx-form",
        hx_swap="outerHTML",
        id="ctx-form",
    )

    return Div(
        Div(
            H1(Span("soco"), " cli"),
            Span(f"{total}", cls="badge"),
            cls="left-header",
        ),
        int_dots,
        chat_history_section(uid, current_sid),
        Div(*groups, cls="left-body"),
        ctx_form,
        cls="left-pane", id="left-pane",
    )


def chat_messages_div(sid: str = ""):
    """Render messages container, pre-populated if loading existing chat."""
    msgs = chat_sessions.get(sid, [])
    children = []
    for m in msgs:
        role_cls = "msg-user" if m["role"] == "user" else "msg-assistant"
        children.append(
            Div(Div(m["content"], cls="msg-bubble"), cls=f"msg {role_cls}")
        )
    return Div(*children, id="messages", cls="messages")


def suggestion_buttons():
    suggestions = [
        "Generate a Twitter post about AI trends",
        "Create a launch plan for my SaaS",
        "Audit SEO for tendly.eu",
        "Write cold email for enterprise leads",
    ]
    return Div(
        *[Button(s, cls="suggest-btn", onclick=f"fillChat(`{s}`)") for s in suggestions],
        cls="suggestions", id="suggestions",
    )


def thinking_step(step_type, command, body):
    cls = "think-step"
    if step_type == "tool_call":
        cls += " tool-call"
    elif step_type == "error":
        cls += " error"

    return Div(
        Div(f"{step_type}: {command}", cls="think-step-type"),
        Div(body, cls="think-step-body"),
        cls=cls,
    )


# ── Routes ───────────────────────────────────────────────────────────────

@rt("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")

@rt("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})

@rt("/icon.svg")
def icon():
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


@rt("/")
def index(sess, chat: str = ""):
    uid = _ensure_user(sess)

    # Load specific chat if requested
    if chat and chat in chat_sessions:
        sess["sid"] = chat
    sid = _ensure_session(sess)

    # Hide suggestions if chat already has messages
    has_messages = bool(chat_sessions.get(sid))

    return Title("soco"), Div(
        # Left pane overlay backdrop
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        # Left pane
        left_pane(uid=uid, current_sid=sid),
        # Center pane
        Div(
            Div(
                Div(
                    Button("\u2630", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                    Span("soco agent", cls="chat-header-title"),
                    cls="chat-header-left",
                ),
                Div(
                    Button("\u2B06", cls="share-btn", onclick="shareChat()",
                           title="Share chat"),
                    Span("0", id="think-count", cls="think-badge"),
                    Button("Thinking", id="think-btn", cls="think-btn active",
                           onclick="toggleThinking()"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            chat_messages_div(sid),
            suggestion_buttons() if not has_messages else Div(id="suggestions"),
            Form(
                Textarea(
                    id="chat-input", name="msg",
                    cls="chat-textarea",
                    placeholder="Ask me anything about marketing...",
                    rows="1",
                    onkeydown="handleKey(event)",
                    oninput="autoResize(this)",
                ),
                Button("Send", type="submit", cls="chat-send", id="send-btn"),
                cls="chat-form",
                onsubmit="sendMessage(event)",
            ),
            cls="center-pane",
        ),
        # Right pane (thinking trace)
        Div(
            Div(
                H3("Thinking Trace"),
                Button("x", cls="right-close", onclick="toggleThinking()"),
                cls="right-header",
            ),
            Div(id="thinking-steps", cls="right-body"),
            id="right-pane", cls="right-pane open",
        ),
        # Share toast
        Div("Link copied!", id="share-toast", cls="share-toast"),
        cls="app",
    ), Script("""
        function toggleGroup(id) {
            const el = document.getElementById(id);
            const btn = document.getElementById('btn-' + id);
            if (el) el.classList.toggle('open');
            if (btn) btn.classList.toggle('open');
        }
        function toggleThinking() {
            const rp = document.getElementById('right-pane');
            const tb = document.getElementById('think-btn');
            if (!rp || !tb) return;
            if (window.innerWidth < 768) return; // no-op on mobile
            rp.classList.toggle('open');
            tb.classList.toggle('active');
            document.querySelector('.app').classList.toggle('pane-closed');
        }
        function toggleLeftPane() {
            const lp = document.getElementById('left-pane');
            const ov = document.getElementById('left-overlay');
            if (!lp) return;
            lp.classList.toggle('open');
            if (ov) ov.classList.toggle('visible');
        }
        function fillChat(text) {
            const input = document.getElementById('chat-input');
            if (input) { input.value = text; input.focus(); autoResize(input); }
            // Close left pane on mobile after selection
            if (window.innerWidth <= 1024) {
                const lp = document.getElementById('left-pane');
                const ov = document.getElementById('left-overlay');
                if (lp) lp.classList.remove('open');
                if (ov) ov.classList.remove('visible');
            }
        }
        function autoResize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 128) + 'px';
            el.style.overflowY = el.scrollHeight > 128 ? 'auto' : 'hidden';
        }
        function handleKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const form = e.target.closest('form');
                if (form && e.target.value.trim()) form.requestSubmit();
            }
        }
        function scrollChat() {
            const m = document.getElementById('messages');
            if (m) m.scrollTop = m.scrollHeight;
        }
        function escapeHtml(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }
        function addThinkStep(cls, title, body) {
            const steps = document.getElementById('thinking-steps');
            if (!steps) return;
            const step = document.createElement('div');
            step.className = 'think-step ' + cls;
            step.innerHTML = '<div class="think-step-type">' + escapeHtml(title) + '</div>'
                + '<div class="think-step-body">' + escapeHtml(body) + '</div>';
            steps.appendChild(step);
            steps.scrollTop = steps.scrollHeight;
        }
        function loadChat(sid) {
            window.location.href = '/?chat=' + encodeURIComponent(sid);
        }
        function newChat() {
            fetch('/chat/new', { method: 'POST' })
                .then(r => r.json())
                .then(d => { window.location.href = '/?chat=' + d.sid; });
        }
        async function shareChat() {
            try {
                const resp = await fetch('/chat/share', { method: 'POST' });
                const data = await resp.json();
                if (data.url) {
                    await navigator.clipboard.writeText(data.url);
                    const toast = document.getElementById('share-toast');
                    if (toast) {
                        toast.classList.add('show');
                        setTimeout(() => toast.classList.remove('show'), 2500);
                    }
                }
            } catch (err) {
                console.error('Share failed:', err);
            }
        }
        async function sendMessage(e) {
            e.preventDefault();
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if (!msg) return;

            const sendBtn = document.getElementById('send-btn');
            sendBtn.disabled = true;
            input.value = '';
            autoResize(input);

            // Hide suggestions after first message
            const sug = document.getElementById('suggestions');
            if (sug) sug.style.display = 'none';

            const messages = document.getElementById('messages');

            // User bubble
            const userDiv = document.createElement('div');
            userDiv.className = 'msg msg-user';
            userDiv.innerHTML = '<div class="msg-bubble">' + escapeHtml(msg) + '</div>';
            messages.appendChild(userDiv);
            scrollChat();

            // Assistant bubble (streaming)
            const asstDiv = document.createElement('div');
            asstDiv.className = 'msg msg-assistant';
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble streaming';
            asstDiv.appendChild(bubble);
            messages.appendChild(asstDiv);
            scrollChat();

            let badgeN = 0;
            try {
                const fd = new FormData();
                fd.append('msg', msg);
                const resp = await fetch('/chat', { method: 'POST', body: fd });
                const reader = resp.body.getReader();
                const dec = new TextDecoder();
                let buf = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buf += dec.decode(value, { stream: true });

                    const parts = buf.split('\\n\\n');
                    buf = parts.pop();

                    for (const part of parts) {
                        if (!part.trim()) continue;
                        const lines = part.trim().split('\\n');
                        let evtType = '', evtData = '';
                        for (const ln of lines) {
                            if (ln.startsWith('event: ')) evtType = ln.slice(7);
                            else if (ln.startsWith('data: ')) evtData = ln.slice(6);
                        }
                        if (!evtType || !evtData) continue;
                        const data = JSON.parse(evtData);

                        if (evtType === 'token') {
                            // Clear ETA placeholder on first real token
                            if (bubble.dataset.eta) { bubble.textContent = ''; delete bubble.dataset.eta; }
                            bubble.textContent += data.text;
                            scrollChat();
                        } else if (evtType === 'tool_start') {
                            badgeN++;
                            const eta = data.eta || 10;
                            const badge = document.createElement('div');
                            badge.className = 'tool-badge';
                            badge.id = 'badge-' + badgeN;
                            badge.innerHTML = '<span class="dot" style="background:var(--yellow)"></span>'
                                + escapeHtml(data.command)
                                + ' <span style="color:var(--muted);font-size:.65rem;margin-left:.3rem">~' + eta + 's</span>';
                            badge.onclick = toggleThinking;
                            asstDiv.insertBefore(badge, bubble);
                            // Show ETA message in streaming bubble
                            bubble.textContent = 'Working on ' + data.command + '... (~' + eta + 's)';
                            bubble.dataset.eta = '1';
                            addThinkStep('tool-call', 'tool_call: ' + data.command + ' (~' + eta + 's)', 'Args: ' + JSON.stringify(data.args, null, 2));
                            scrollChat();
                        } else if (evtType === 'tool_end') {
                            const badge = document.getElementById('badge-' + badgeN);
                            if (badge) {
                                const dot = badge.querySelector('.dot');
                                if (dot) dot.style.background = data.status === 'success' ? 'var(--green)' : 'var(--red)';
                            }
                            const stepCls = data.status === 'success' ? 'tool-call' : 'error';
                            addThinkStep(stepCls, data.status + ': ' + data.command, (data.output || '').slice(0, 500));
                        } else if (evtType === 'done') {
                            const tc = document.getElementById('think-count');
                            if (tc) tc.textContent = String(data.tool_count || 0);
                        }
                    }
                }
            } catch (err) {
                bubble.textContent += 'Error: ' + err.message;
            }

            bubble.classList.remove('streaming');
            sendBtn.disabled = false;
            input.focus();
            scrollChat();
        }
        // Auto-scroll on new messages
        const obs = new MutationObserver(scrollChat);
        document.addEventListener('DOMContentLoaded', () => {
            const m = document.getElementById('messages');
            if (m) obs.observe(m, {childList: true, subtree: true});
            scrollChat();
            // Enable left-pane transition after first paint (prevents flash)
            requestAnimationFrame(() => {
                document.getElementById('left-pane')?.classList.add('animated');
            });
            // Register service worker
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js').catch(() => {});
            }
        });
    """)


@rt("/chat", methods=["POST"])
async def chat(msg: str, sess):
    if not msg or not msg.strip():
        return ""

    sid = sess.get("sid", "default")
    if sid not in chat_sessions:
        chat_sessions[sid] = []

    user_msg = msg.strip()
    chat_sessions[sid].append({"role": "user", "content": user_msg})
    history = list(chat_sessions[sid][:-1])

    return StreamingResponse(
        agent_chat_stream(user_msg, history, chat_sessions[sid]),
        media_type="text/event-stream",
    )


@rt("/chat/new", methods=["POST"])
def chat_new(sess):
    uid = _ensure_user(sess)
    new_sid = str(uuid.uuid4())
    sess["sid"] = new_sid
    chat_sessions[new_sid] = []
    if uid not in user_chats:
        user_chats[uid] = []
    user_chats[uid].insert(0, new_sid)
    return {"sid": new_sid}


@rt("/chat/share", methods=["POST"])
def chat_share(sess, req):
    sid = sess.get("sid")
    if not sid or sid not in chat_sessions or not chat_sessions[sid]:
        return {"error": "No chat to share"}

    # Check if already shared
    for share_id, linked_sid in shared_chats.items():
        if linked_sid == sid:
            url = f"{req.base_url}s/{share_id}"
            return {"url": url, "share_id": share_id}

    share_id = uuid.uuid4().hex[:10]
    shared_chats[share_id] = sid
    url = f"{req.base_url}s/{share_id}"
    return {"url": url, "share_id": share_id}


@rt("/s/{share_id}")
def shared_view(share_id: str):
    sid = shared_chats.get(share_id)
    if not sid or sid not in chat_sessions:
        return Title("Not found"), Div(
            H2("Chat not found", style="text-align:center;padding:4rem;color:var(--muted);"),
        )

    msgs = chat_sessions[sid]
    msg_els = []
    for m in msgs:
        role_cls = "msg-user" if m["role"] == "user" else "msg-assistant"
        msg_els.append(
            Div(Div(m["content"], cls="msg-bubble"), cls=f"msg {role_cls}")
        )

    return Title("Shared Chat — soco"), css, Div(
        Div(
            Div(
                Span("\u25C6", style="color:var(--accent);font-size:1.1rem;"),
                Span("Shared conversation", style="font-weight:600;font-size:.9rem;"),
                cls="share-header-title",
            ),
            Div(
                A("Open in Soco", href="/", cls="share-link-btn"),
                Button("Copy text", cls="share-copy-btn", onclick="copyChat()"),
                cls="share-header-actions",
            ),
            cls="share-header",
        ),
        Div(*msg_els, cls="share-messages"),
        Div(id="share-toast", cls="share-toast"),
        cls="share-page",
    ), Script("""
        function copyChat() {
            const msgs = document.querySelectorAll('.msg');
            let text = '';
            msgs.forEach(m => {
                const role = m.classList.contains('msg-user') ? 'You' : 'Soco';
                const bubble = m.querySelector('.msg-bubble');
                if (bubble) text += role + ': ' + bubble.textContent.trim() + '\\n\\n';
            });
            navigator.clipboard.writeText(text.trim()).then(() => {
                const toast = document.getElementById('share-toast');
                if (toast) {
                    toast.textContent = 'Copied!';
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2500);
                }
            });
        }
    """)


@rt("/context", methods=["POST"])
def save_context(company: str = "", product: str = "", audience: str = "", tone: str = ""):
    soco_ctx.product.company = company
    soco_ctx.product.product = product
    soco_ctx.product.audience = audience
    soco_ctx.product.tone = tone or "professional"

    return Form(
        H4("Product Context"),
        *[Div(
            Label(k.title()), Input(name=k, value=v, placeholder=k),
            cls="ctx-mini-field",
        ) for k, v in [("company", company), ("product", product),
                       ("audience", audience), ("tone", tone or "professional")]],
        Button("Saved!", cls="ctx-save", type="submit", style="background:var(--green);color:#fff;"),
        cls="ctx-sidebar",
        hx_post="/context",
        hx_target="#ctx-form",
        hx_swap="outerHTML",
        id="ctx-form",
    )


# ── Serve ────────────────────────────────────────────────────────────────

serve(port=5001)
