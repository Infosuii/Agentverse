"""Policy parser and scope gate. Owner: agent-5."""
from .parser import parse_policy
from .scope import check_scope

__all__ = ["check_scope", "parse_policy"]
