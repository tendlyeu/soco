"""Session context holding shared state across agents."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProductContext:
    """Shared product context that all agents can read for LLM prompt injection."""
    company: str = ""
    product: str = ""
    audience: str = ""
    tone: str = "professional"
    industry: str = ""
    website: str = ""
    competitors: list[str] = field(default_factory=list)
    value_proposition: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def is_set(self) -> bool:
        return bool(self.company or self.product)

    def to_prompt_block(self) -> str:
        """Render as a block suitable for injecting into LLM system prompts."""
        if not self.is_set():
            return ""
        lines = ["Product Context:"]
        if self.company:
            lines.append(f"  Company: {self.company}")
        if self.product:
            lines.append(f"  Product: {self.product}")
        if self.audience:
            lines.append(f"  Target Audience: {self.audience}")
        if self.tone:
            lines.append(f"  Tone: {self.tone}")
        if self.industry:
            lines.append(f"  Industry: {self.industry}")
        if self.website:
            lines.append(f"  Website: {self.website}")
        if self.competitors:
            lines.append(f"  Competitors: {', '.join(self.competitors)}")
        if self.value_proposition:
            lines.append(f"  Value Proposition: {self.value_proposition}")
        for k, v in self.extra.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def set_from_args(self, args: dict[str, str]) -> list[str]:
        """Set fields from key:value args. Returns list of fields that were set."""
        set_fields = []
        known = {
            "company", "product", "audience", "tone", "industry",
            "website", "value_proposition", "value-proposition",
        }
        for key, value in args.items():
            normalized = key.replace("-", "_")
            if normalized == "competitors":
                self.competitors = [c.strip() for c in value.split(",")]
                set_fields.append("competitors")
            elif normalized in known:
                setattr(self, normalized, value)
                set_fields.append(normalized)
            else:
                self.extra[key] = value
                set_fields.append(key)
        return set_fields


class SessionContext:
    """Holds integration clients and shared state for a soco session."""

    def __init__(self):
        self.product = ProductContext()
        self.scratch: dict[str, Any] = {}
        self._integrations: dict[str, Any] = {}

    def get_integration(self, name: str) -> Optional[Any]:
        return self._integrations.get(name)

    def set_integration(self, name: str, client: Any) -> None:
        self._integrations[name] = client

    @property
    def xai(self) -> Optional[Any]:
        return self._integrations.get("xai")

    @property
    def arcade(self) -> Optional[Any]:
        return self._integrations.get("arcade")

    @property
    def playwright(self) -> Optional[Any]:
        return self._integrations.get("playwright")

    @property
    def composio(self) -> Optional[Any]:
        return self._integrations.get("composio")
