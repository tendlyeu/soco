"""Soco Marketing CLI — 3-Pane Agentic FastHTML Web UI."""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

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

    product_block = ctx.product.to_prompt_block() or "Not set"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(product_context=product_block)

    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)


async def agent_chat(user_msg: str, history: list) -> tuple[str, list]:
    """Run the LangGraph ReAct agent loop."""
    graph = build_agent(registry, soco_ctx)
    if graph is None:
        return "XAI integration not configured. Set XAI_API_KEY in .env", []

    # Convert history to LangChain message objects
    messages = []
    for h in history[-20:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_msg))

    # Invoke the ReAct agent
    result = await graph.ainvoke({"messages": messages})

    # Extract tool calls for thinking trace
    tool_calls_trace = []
    for msg in result["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                # Convert name back from agent__tool to agent:tool
                cmd = tc["name"].replace("__", ":", 1)
                tool_calls_trace.append({
                    "command": cmd,
                    "args": tc.get("args", {}),
                    "status": "pending",
                    "output": "",
                })
        elif isinstance(msg, ToolMessage):
            # Match tool result back to pending trace entry
            for entry in tool_calls_trace:
                if entry["status"] == "pending":
                    is_error = msg.status == "error" if hasattr(msg, "status") else False
                    entry["status"] = "error" if is_error else "success"
                    entry["output"] = msg.content[:2000] if msg.content else ""
                    break

    # Final AI reply is the last AIMessage without tool_calls
    reply = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            reply = msg.content
            break

    return reply or "I processed your request but have no additional commentary.", tool_calls_trace


# ── In-memory chat store ─────────────────────────────────────────────────

chat_sessions: dict[str, list] = {}  # session_id -> [{role, content}]

# ── CSS ──────────────────────────────────────────────────────────────────

css = Style("""
:root {
    --bg: #f9fafb; --surface: #ffffff; --surface2: #f3f4f6;
    --border: #e5e7eb; --text: #111827; --muted: #6b7280;
    --accent: #2563eb; --accent2: #7c3aed; --green: #16a34a;
    --red: #dc2626; --yellow: #d97706;
    --gradient: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
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
}

/* ── Left Pane: Tools Reference ────────────────────────────────── */
.left-pane {
    background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
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

/* ── Center Pane: Chat ─────────────────────────────────────────── */
.center-pane {
    display: flex; flex-direction: column; overflow: hidden;
    position: relative; background: var(--bg);
}
.chat-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: .65rem 1.25rem; background: var(--surface);
    border-bottom: 1px solid var(--border); min-height: 2.75rem;
    position: relative; z-index: 101;
}
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

/* Messages area */
.messages {
    flex: 1; overflow-y: auto; padding: 1.25rem;
    display: flex; flex-direction: column; gap: .75rem;
}
.messages:empty::before {
    content: "Ask me anything about marketing — I'll pick the right tool and get it done.";
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

/* ── Responsive ────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .app { grid-template-columns: 1fr; }
    .left-pane { display: none; }
    .right-pane { width: 100%; right: -100%; }
}
""")

fonts = (
    Link(rel="preconnect", href="https://fonts.googleapis.com"),
    Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"),
)

app, rt = fast_app(
    pico=False,
    hdrs=[css, *fonts, Script(src="https://unpkg.com/htmx.org@2.0.4")],
    secret_key=os.getenv("SESSION_SECRET", "soco-dev-key-change-me"),
)

# ── Components ───────────────────────────────────────────────────────────

def left_pane():
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
        Div(*groups, cls="left-body"),
        ctx_form,
        cls="left-pane",
    )


def chat_messages_div():
    return Div(id="messages", cls="messages")


def suggestion_buttons():
    suggestions = [
        "Generate a Twitter post about AI trends",
        "Create a launch plan for my SaaS",
        "Audit SEO for tendly.eu",
        "Write cold email for enterprise leads",
    ]
    return Div(
        *[Button(s, cls="suggest-btn", onclick=f"fillChat(`{s}`)") for s in suggestions],
        cls="suggestions",
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

@rt("/")
def index(sess):
    if "sid" not in sess:
        sess["sid"] = str(uuid.uuid4())
    sid = sess["sid"]
    if sid not in chat_sessions:
        chat_sessions[sid] = []

    return Title("soco"), Div(
        # Left pane
        left_pane(),
        # Center pane
        Div(
            Div(
                Span("soco agent", cls="chat-header-title"),
                Div(
                    Span("0", id="think-count", cls="think-badge"),
                    Button("Thinking", id="think-btn", cls="think-btn",
                           onclick="toggleThinking()"),
                    cls="chat-header-actions",
                ),
                cls="chat-header",
            ),
            chat_messages_div(),
            suggestion_buttons(),
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
                hx_post="/chat",
                hx_target="#messages",
                hx_swap="beforeend",
                hx_disabled_elt="#send-btn",
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
            id="right-pane", cls="right-pane",
        ),
        cls="app",
    ), Script("""
        function toggleGroup(id) {
            const el = document.getElementById(id);
            const btn = document.getElementById('btn-' + id);
            el.classList.toggle('open');
            btn.classList.toggle('open');
        }
        function toggleThinking() {
            document.getElementById('right-pane').classList.toggle('open');
            document.getElementById('think-btn').classList.toggle('active');
        }
        function fillChat(text) {
            const input = document.getElementById('chat-input');
            if (input) { input.value = text; input.focus(); autoResize(input); }
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
        // Auto-scroll on new messages
        const obs = new MutationObserver(scrollChat);
        document.addEventListener('DOMContentLoaded', () => {
            const m = document.getElementById('messages');
            if (m) obs.observe(m, {childList: true, subtree: true});
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

    # User message bubble
    user_bubble = Div(
        Div(user_msg, cls="msg-bubble"),
        cls="msg msg-user",
    )

    # Run agent
    try:
        reply, tool_calls = await agent_chat(user_msg, chat_sessions[sid][:-1])
    except Exception as e:
        reply = f"Error: {e}"
        tool_calls = []

    chat_sessions[sid].append({"role": "assistant", "content": reply})

    # Tool call badges
    badges = []
    for tc in tool_calls:
        dot_cls = "dot success" if tc["status"] == "success" else "dot error"
        badges.append(
            Div(Span(cls=dot_cls), tc["command"], cls="tool-badge",
                onclick="toggleThinking()")
        )

    # Thinking panel OOB update
    think_steps = []
    for tc in tool_calls:
        step_type = "tool_call" if tc["status"] == "success" else "error"
        think_steps.append(thinking_step(step_type, tc["command"],
                                          tc.get("output", "")[:500]))

    oob_thinking = Div(
        *think_steps,
        id="thinking-steps",
        hx_swap_oob="beforeend",
    ) if think_steps else ""

    oob_badge_count = Span(
        str(len(tool_calls)),
        id="think-count",
        cls="think-badge",
        hx_swap_oob="outerHTML",
    ) if tool_calls else ""

    # Assistant message bubble
    assistant_bubble = Div(
        *badges,
        Div(reply, cls="msg-bubble"),
        cls="msg msg-assistant",
    )

    return user_bubble, assistant_bubble, oob_thinking, oob_badge_count


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
