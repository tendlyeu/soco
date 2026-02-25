"""Content agent — Content creation, copywriting, email sequences."""
from datetime import date

from agents.base import BaseAgent, ToolDefinition, ToolResult, ToolStatus


SYSTEM_PROMPT_BASE = (
    "You are an expert marketing copywriter and content strategist. "
    f"Today's date is {date.today()}. Always produce content that is current and relevant — "
    "reference recent trends, data, and events. Never cite outdated years or stale statistics."
)


class ContentAgent(BaseAgent):
    name = "content"
    description = "Content creation, copywriting, email sequences"

    def get_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="copywriting",
                description="Generate marketing copy for any format",
                long_help="Generate marketing copy for headlines, landing pages, CTAs, and more. "
                          "Powered by XAI/Grok. Respects product context if set.",
                aliases=["copy"],
                examples=[
                    'content:copywriting topic:"SaaS landing page hero" format:headline',
                    'content:copywriting topic:"Feature announcement" tone:casual',
                    'content:copywriting topic:"Pricing page value prop" format:bullet',
                ],
                required_integrations=["xai"],
                parameters={
                    "topic": {"description": "What to write about", "required": True},
                    "format": {"description": "Output format", "required": False, "default": "paragraph", "options": ["headline", "paragraph", "bullet", "cta"]},
                    "tone": {"description": "Writing tone", "required": False, "default": "professional", "options": ["professional", "casual", "urgent", "friendly"]},
                    "platform": {"description": "Target platform", "required": False, "default": "web", "options": ["web", "email", "social"]},
                },
            ),
            ToolDefinition(
                name="copy-editing",
                description="Review and improve existing copy",
                long_help="Analyze existing copy and provide improvements for clarity, persuasion, and conciseness.",
                aliases=["edit"],
                examples=[
                    'content:copy-editing input:"Our product helps businesses grow faster with AI."',
                    'content:edit input:"Sign up now for free" goal:persuasion',
                ],
                required_integrations=["xai"],
                parameters={
                    "input": {"description": "The copy to review and improve", "required": True},
                    "goal": {"description": "Editing focus", "required": False, "default": "all", "options": ["clarity", "persuasion", "conciseness", "all"]},
                },
            ),
            ToolDefinition(
                name="social-content",
                description="Platform-optimized social media posts",
                long_help="Generate social media posts optimized for specific platforms. "
                          "X posts are kept under 280 chars, LinkedIn posts are long-form professional.",
                aliases=["social"],
                examples=[
                    'content:social-content platform:x topic:"product launch"',
                    'content:social-content platform:linkedin topic:"hiring announcement"',
                ],
                required_integrations=["xai"],
                parameters={
                    "topic": {"description": "What to post about", "required": True},
                    "platform": {"description": "Target social platform", "required": False, "default": "x", "options": ["x", "linkedin", "both"]},
                    "tone": {"description": "Writing tone", "required": False, "default": "professional"},
                },
            ),
            ToolDefinition(
                name="email-sequence",
                description="Multi-step email drip sequences",
                long_help="Design multi-step email drip sequences with subject lines, body copy, and timing recommendations.",
                aliases=["email"],
                examples=[
                    "content:email-sequence type:onboarding steps:5",
                    'content:email topic:"trial expiring" type:retention steps:3',
                ],
                required_integrations=["xai"],
                parameters={
                    "type": {"description": "Sequence type", "required": False, "default": "onboarding", "options": ["onboarding", "nurture", "retention", "upsell", "reactivation"]},
                    "topic": {"description": "Email sequence topic/trigger", "required": False},
                    "steps": {"description": "Number of emails in sequence", "required": False, "default": "5"},
                },
            ),
            ToolDefinition(
                name="cold-email",
                description="B2B prospecting email sequences",
                long_help="Generate B2B cold email sequences with personalization placeholders, subject lines, and follow-ups.",
                aliases=["cold"],
                examples=[
                    'content:cold-email target:"SaaS CTOs" product:"analytics platform" steps:3',
                ],
                required_integrations=["xai"],
                parameters={
                    "target": {"description": "Target persona/role", "required": True},
                    "product": {"description": "Product being pitched", "required": False},
                    "steps": {"description": "Number of emails in sequence", "required": False, "default": "3"},
                    "tone": {"description": "Writing tone", "required": False, "default": "professional"},
                },
            ),
            ToolDefinition(
                name="ad-creative",
                description="Ad headlines and descriptions for ad platforms",
                long_help="Generate ad creative (headlines, descriptions) optimized for Google, Meta, LinkedIn, or TikTok ads.",
                aliases=["ads"],
                examples=[
                    'content:ad-creative platform:google topic:"project management tool" format:responsive',
                    'content:ad-creative platform:meta topic:"fitness app" audience:"millennials"',
                ],
                required_integrations=["xai"],
                parameters={
                    "topic": {"description": "What to advertise", "required": True},
                    "platform": {"description": "Ad platform", "required": False, "default": "google", "options": ["google", "meta", "linkedin", "tiktok"]},
                    "format": {"description": "Ad format", "required": False, "default": "standard", "options": ["standard", "responsive", "carousel"]},
                    "audience": {"description": "Target audience description", "required": False},
                },
            ),
            ToolDefinition(
                name="content-strategy",
                description="Content planning, topic clusters, keyword mapping",
                long_help="Develop a content strategy including topic clusters, keyword mapping, content calendar ideas, and distribution plan.",
                aliases=["plan"],
                examples=[
                    'content:content-strategy topic:"B2B SaaS marketing" months:3',
                    'content:plan topic:"developer tools" format:calendar',
                ],
                required_integrations=["xai"],
                parameters={
                    "topic": {"description": "Main topic or business area", "required": True},
                    "months": {"description": "Planning horizon in months", "required": False, "default": "3"},
                    "format": {"description": "Output format", "required": False, "default": "strategy", "options": ["strategy", "calendar", "clusters"]},
                },
            ),
        ]

    async def execute(self, tool_name: str, args: dict[str, str], context) -> ToolResult:
        xai = context.get_integration("xai")
        if not xai:
            return ToolResult(status=ToolStatus.ERROR, error="XAI integration not configured. Set XAI_API_KEY in .env")

        tool = self.resolve_tool(tool_name)
        # Check required params
        for pname, pinfo in (tool.parameters if tool else {}).items():
            if pinfo.get("required") and pname not in args:
                return ToolResult(status=ToolStatus.NEEDS_INPUT, follow_up_prompt=f"Missing required parameter: {pname}")

        product_block = context.product.to_prompt_block() if context.product.is_set() else ""

        if tool_name == "copywriting":
            return await self._copywriting(args, xai, product_block)
        elif tool_name == "copy-editing":
            return await self._copy_editing(args, xai, product_block)
        elif tool_name == "social-content":
            return await self._social_content(args, xai, product_block)
        elif tool_name == "email-sequence":
            return await self._email_sequence(args, xai, product_block)
        elif tool_name == "cold-email":
            return await self._cold_email(args, xai, product_block)
        elif tool_name == "ad-creative":
            return await self._ad_creative(args, xai, product_block)
        elif tool_name == "content-strategy":
            return await self._content_strategy(args, xai, product_block)

        return ToolResult(status=ToolStatus.ERROR, error=f"Unknown tool: {tool_name}")

    async def _copywriting(self, args, xai, product_block) -> ToolResult:
        topic = args["topic"]
        fmt = args.get("format", "paragraph")
        tone = args.get("tone", "professional")
        platform = args.get("platform", "web")

        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Generate {fmt} format marketing copy. Tone: {tone}. Target platform: {platform}."""

        user_prompt = f"Write marketing copy about: {topic}"
        output = await xai.generate(system, user_prompt)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _copy_editing(self, args, xai, product_block) -> ToolResult:
        text = args.get("input", "")
        goal = args.get("goal", "all")

        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
You are reviewing and improving existing copy. Focus: {goal}.
Provide the improved version followed by a brief explanation of changes."""

        output = await xai.generate(system, f"Improve this copy:\n\n{text}")
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _social_content(self, args, xai, product_block) -> ToolResult:
        topic = args["topic"]
        platform = args.get("platform", "x")
        tone = args.get("tone", "professional")

        platforms = ["x", "linkedin"] if platform == "both" else [platform]
        outputs = []

        for p in platforms:
            if p == "x":
                constraint = "Maximum 280 characters. Punchy and engaging."
            else:
                constraint = "2-3 paragraphs. Professional LinkedIn style."

            system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Generate a {p.upper()} social media post. {constraint} Tone: {tone}.
Include relevant hashtags."""

            result = await xai.generate(system, f"Write a social post about: {topic}")
            outputs.append(f"--- {p.upper()} ---\n{result}")

        return ToolResult(status=ToolStatus.SUCCESS, output="\n\n".join(outputs))

    async def _email_sequence(self, args, xai, product_block) -> ToolResult:
        seq_type = args.get("type", "onboarding")
        topic = args.get("topic", seq_type)
        steps = args.get("steps", "5")

        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Design a {steps}-step {seq_type} email sequence.
For each email include: subject line, preview text, body copy, CTA, and recommended send timing."""

        output = await xai.generate(system, f"Create an email sequence for: {topic}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _cold_email(self, args, xai, product_block) -> ToolResult:
        target = args["target"]
        product = args.get("product", "")
        steps = args.get("steps", "3")
        tone = args.get("tone", "professional")

        product_desc = f"Product: {product}" if product else ""
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Write a {steps}-step B2B cold email sequence. Tone: {tone}.
Target: {target}. {product_desc}
Include personalization placeholders like {{first_name}}, {{company}}.
For each email: subject line, body, CTA. Include follow-up timing."""

        output = await xai.generate(system, f"Cold email sequence targeting: {target}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _ad_creative(self, args, xai, product_block) -> ToolResult:
        topic = args["topic"]
        platform = args.get("platform", "google")
        fmt = args.get("format", "standard")
        audience = args.get("audience", "")

        audience_note = f"Target audience: {audience}" if audience else ""
        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
Generate {fmt} ad creative for {platform.title()} Ads.
{audience_note}
Include multiple headline variants, descriptions, and CTAs.
Follow {platform} ad specs and character limits."""

        output = await xai.generate(system, f"Create ad creative for: {topic}")
        return ToolResult(status=ToolStatus.SUCCESS, output=output)

    async def _content_strategy(self, args, xai, product_block) -> ToolResult:
        topic = args["topic"]
        months = args.get("months", "3")
        fmt = args.get("format", "strategy")

        format_instruction = {
            "strategy": "Provide a comprehensive content strategy with goals, audience analysis, topic clusters, keywords, and distribution channels.",
            "calendar": "Provide a month-by-month content calendar with specific post topics, formats, and channels.",
            "clusters": "Provide topic clusters with pillar content and supporting articles, including keyword targets.",
        }.get(fmt, "Provide a comprehensive content strategy.")

        system = f"""{SYSTEM_PROMPT_BASE}
{product_block}
{format_instruction}
Planning horizon: {months} months."""

        output = await xai.generate(system, f"Content strategy for: {topic}", max_tokens=3000)
        return ToolResult(status=ToolStatus.SUCCESS, output=output)
