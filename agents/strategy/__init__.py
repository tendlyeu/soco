"""Strategy agent — Launch planning, pricing, marketing psychology."""
from datetime import date

from agents.base import BaseAgent, ToolDefinition, ToolResult, ToolStatus


SYSTEM_PROMPT_BASE = (
    "You are an expert SaaS marketing strategist and growth advisor. "
    f"Today's date is {date.today()}. Always produce content that is current and relevant — "
    "reference recent trends, data, and events. Never cite outdated years or stale statistics."
)


class StrategyAgent(BaseAgent):
    name = "strategy"
    description = "Launch planning, pricing, marketing psychology"

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="launch",
                description="Product launch planning",
                long_help="Create a comprehensive product launch plan using the ORB framework. "
                          "Includes pre-launch, launch day, and post-launch phases with channel strategies.",
                aliases=["go-to-market", "gtm"],
                examples=[
                    'strategy:launch product:"AI analytics tool" stage:pre-launch',
                    'strategy:launch product:"mobile app" channels:ph,twitter,email',
                ],
                required_integrations=["xai"],
                parameters={
                    "product": {"description": "Product being launched", "required": True},
                    "stage": {"description": "Launch phase", "required": False, "default": "full", "options": ["pre-launch", "launch-day", "post-launch", "full"]},
                    "channels": {"description": "Comma-separated launch channels", "required": False},
                },
                estimated_seconds=20,
            ),
            ToolDefinition(
                name="pricing",
                description="Pricing strategy and packaging",
                long_help="Develop pricing strategy and packaging recommendations based on market positioning, "
                          "value metrics, competitor analysis, and pricing psychology.",
                aliases=["price"],
                examples=[
                    'strategy:pricing product:"project management SaaS" model:freemium',
                    'strategy:pricing product:"API service" competitors:"Stripe,Square"',
                ],
                required_integrations=["xai"],
                parameters={
                    "product": {"description": "Product to price", "required": True},
                    "model": {"description": "Pricing model", "required": False, "options": ["freemium", "tiered", "usage-based", "flat-rate", "hybrid"]},
                    "competitors": {"description": "Comma-separated competitor names", "required": False},
                },
                estimated_seconds=20,
            ),
            ToolDefinition(
                name="referral",
                description="Design referral and affiliate programs",
                long_help="Design a referral or affiliate program with incentive structures, "
                          "viral mechanics, tracking recommendations, and growth projections.",
                aliases=["affiliate"],
                examples=[
                    'strategy:referral product:"SaaS platform" type:two-sided',
                    'strategy:referral product:"marketplace" incentive:credit',
                ],
                required_integrations=["xai"],
                parameters={
                    "product": {"description": "Product for referral program", "required": True},
                    "type": {"description": "Program type", "required": False, "default": "two-sided", "options": ["one-sided", "two-sided", "tiered", "affiliate"]},
                    "incentive": {"description": "Incentive type", "required": False, "default": "discount", "options": ["discount", "credit", "cash", "feature-unlock"]},
                },
                estimated_seconds=15,
            ),
            ToolDefinition(
                name="product-context",
                description="Set or view shared product context",
                long_help="Set or view the shared product context that all agents use for personalized output. "
                          "Use 'set' as first arg to update context, or omit to view current context.",
                aliases=["ctx"],
                examples=[
                    'strategy:product-context set company:Tendly product:"Tender platform" audience:"procurement teams"',
                    "strategy:product-context",
                ],
                required_integrations=[],
                parameters={
                    "set": {"description": "Action: include 'set' to update context", "required": False},
                    "company": {"description": "Company name", "required": False},
                    "product": {"description": "Product name/description", "required": False},
                    "audience": {"description": "Target audience", "required": False},
                    "tone": {"description": "Default tone", "required": False},
                    "industry": {"description": "Industry vertical", "required": False},
                    "website": {"description": "Company website", "required": False},
                    "competitors": {"description": "Comma-separated competitor names", "required": False},
                    "value-proposition": {"description": "Core value proposition", "required": False},
                },
                estimated_seconds=1,
            ),
            ToolDefinition(
                name="ideas",
                description="Generate marketing ideas",
                long_help="Brainstorm marketing ideas for SaaS/software products. "
                          "Generates actionable ideas across channels with effort/impact scoring.",
                aliases=["brainstorm"],
                examples=[
                    'strategy:ideas topic:"user acquisition" count:10',
                    'strategy:ideas topic:"retention" channel:email',
                ],
                required_integrations=["xai"],
                parameters={
                    "topic": {"description": "Marketing area or challenge", "required": True},
                    "count": {"description": "Number of ideas", "required": False, "default": "10"},
                    "channel": {"description": "Focus on specific channel", "required": False},
                },
                estimated_seconds=20,
            ),
            ToolDefinition(
                name="psychology",
                description="Apply behavioral science to marketing",
                long_help="Apply 70+ behavioral science principles (Cialdini, Kahneman, etc.) to marketing. "
                          "Get specific, actionable recommendations for applying psychology principles.",
                aliases=["psych", "behavioral"],
                examples=[
                    'strategy:psychology principle:scarcity context:"pricing page"',
                    'strategy:psychology context:"onboarding flow" goal:activation',
                ],
                required_integrations=["xai"],
                parameters={
                    "context": {"description": "Where to apply psychology (page, flow, campaign)", "required": True},
                    "principle": {"description": "Specific principle to apply", "required": False},
                    "goal": {"description": "Desired outcome", "required": False, "options": ["conversion", "retention", "activation", "referral"]},
                },
                estimated_seconds=20,
            ),
        ]

    async def execute(self, tool_name: str, args: dict[str, str], context) -> ToolResult:
        # product-context is special — no XAI needed
        if tool_name == "product-context":
            return self._product_context(args, context)

        xai = context.get_integration("xai")
        if not xai:
            return ToolResult(status=ToolStatus.ERROR, error="XAI integration not configured. Set XAI_API_KEY in .env")

        tool = self.resolve_tool(tool_name)
        for pname, pinfo in (tool.parameters if tool else {}).items():
            if pinfo.get("required") and pname not in args:
                return ToolResult(status=ToolStatus.NEEDS_INPUT, follow_up_prompt=f"Missing required parameter: {pname}")

        product_block = context.product.to_prompt_block() if context.product.is_set() else ""

        if tool_name == "launch":
            return await self._launch(args, xai, product_block)
        elif tool_name == "pricing":
            return await self._pricing(args, xai, product_block)
        elif tool_name == "referral":
            return await self._referral(args, xai, product_block)
        elif tool_name == "ideas":
            return await self._ideas(args, xai, product_block)
        elif tool_name == "psychology":
            return await self._psychology(args, xai, product_block)

        return ToolResult(status=ToolStatus.ERROR, error=f"Unknown tool: {tool_name}")

    def _product_context(self, args: dict[str, str], context) -> ToolResult:
        # If 'set' is present (as key or if any other context keys are present), update
        setting_keys = {"company", "product", "audience", "tone", "industry", "website", "competitors", "value-proposition"}
        context_args = {k: v for k, v in args.items() if k in setting_keys}

        if context_args or "set" in args:
            fields_set = context.product.set_from_args(context_args)
            if fields_set:
                output = f"Updated product context: {', '.join(fields_set)}\n\n{context.product.to_prompt_block()}"
            else:
                output = "No fields provided to set. Use: company:, product:, audience:, etc."
            return ToolResult(status=ToolStatus.SUCCESS, output=output)

        # View mode
        if context.product.is_set():
            return ToolResult(status=ToolStatus.SUCCESS, output=context.product.to_prompt_block())
        else:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output="No product context set yet.\n\nSet it with:\n  strategy:product-context set company:YourCo product:\"Your Product\" audience:\"Target Audience\"",
            )

    async def _launch(self, args, xai, product_block) -> ToolResult:
        product = args["product"]
        stage = args.get("stage", "full")
        channels = args.get("channels", "")

        channel_note = f"Focus channels: {channels}" if channels else "Cover all relevant channels."
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Create a {stage} product launch plan. {channel_note}
Include: timeline, channel strategies, messaging, KPIs, and risk mitigation."""

        output = await xai.generate(system, f"Launch plan for: {product}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _pricing(self, args, xai, product_block) -> ToolResult:
        product = args["product"]
        model = args.get("model", "")
        competitors = args.get("competitors", "")

        model_note = f"Pricing model preference: {model}" if model else "Recommend the best pricing model."
        comp_note = f"Key competitors: {competitors}" if competitors else ""
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Develop a pricing strategy. {model_note} {comp_note}
Include: pricing tiers, feature gates, value metrics, competitive positioning, and pricing psychology."""

        output = await xai.generate(system, f"Pricing strategy for: {product}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _referral(self, args, xai, product_block) -> ToolResult:
        product = args["product"]
        prog_type = args.get("type", "two-sided")
        incentive = args.get("incentive", "discount")

        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Design a {prog_type} referral program with {incentive} incentives.
Include: mechanics, incentive structure, viral loops, tracking setup, and growth projections."""

        output = await xai.generate(system, f"Referral program for: {product}", max_tokens=2000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _ideas(self, args, xai, product_block) -> ToolResult:
        topic = args["topic"]
        count = args.get("count", "10")
        channel = args.get("channel", "")

        channel_note = f"Focus on {channel} channel." if channel else "Cover multiple channels."
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Generate {count} actionable marketing ideas. {channel_note}
For each idea: title, description, effort (low/med/high), impact (low/med/high), channel."""

        output = await xai.generate(system, f"Marketing ideas for: {topic}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _psychology(self, args, xai, product_block) -> ToolResult:
        ctx = args["context"]
        principle = args.get("principle", "")
        goal = args.get("goal", "")

        principle_note = f"Focus on the '{principle}' principle." if principle else "Apply the most relevant behavioral science principles."
        goal_note = f"Goal: {goal}" if goal else ""
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Apply behavioral science and marketing psychology principles.
{principle_note} {goal_note}
Reference specific research (Cialdini, Kahneman, Fogg, etc.).
For each principle: explain it, give specific implementation advice, and provide copy/UX examples."""

        output = await xai.generate(system, f"Apply psychology to: {ctx}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)
