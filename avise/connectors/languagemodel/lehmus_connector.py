"""AVISE connector for the Lehmus platform (University of Oulu).

Lehmus runs on a ConfidentialMind stack fronting a selection of models. The
request API is identical across models; only two inputs vary: the model alias
(e.g. "xyz123abc") sent in the request "model" field, and the API key (created
in the Lehmus portal, binds project and user). One connector therefore covers
the whole selection: pass the alias as the model `name` and the key once. The
alias is resolved per request, so the same instance drives any model the key
authorizes. (If Lehmus issues keys per model rather than per project, switching
alias also means switching key.)

Each endpoint that can carry an attacker-controlled file is modelled as a
separate file-intake channel (see FileIntake), so a SET can target a specific
vector and the report can attribute which one fired:

  rag_chat / rag_tool / rag_ingest  persistent — a file is ingested into the RAG
                                    store and retrieved on a later query.
  files_api                         transient — upload for a file_id, referenced
                                    in one chat request (disabled; not available
                                    on ConfidentialMind).
  inline_content                    transient — file bytes embedded directly in
                                    the message (disabled; not available on
                                    ConfidentialMind).

Plain-text transport remains via generate() — the AVISE pipeline hook — for
direct prompt injection (single- and multi-turn).

Implements BaseLMConnector (connectors/languagemodel/base.py) and registers as
"lehmus-lm". Configured via a `target_model` / `eval_model`
sub-dict; see configs/connector/languagemodel/lehmus.yaml for the fields,
defaults and per-service env fallbacks (<connector_id>_URL / _APIKEY / _MODEL,
and the _RAG_* keys).
"""

from __future__ import annotations

import os
import time
import base64
import logging
import mimetypes
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from .base import BaseLMConnector, Message
from ...registry import connector_registry
from ...utils import ansi_colors

logger = logging.getLogger(__name__)


class FileIntake(str, Enum):
    """File-bearing endpoints, each a distinct indirect-injection vector."""

    RAG_CHAT = "rag_chat"  # primary: ingest -> {rag}/v1/chat/completions (server-side retrieve+generate, RAG's own model)
    RAG_TOOL = "rag_tool"  # ingest -> gateway /v1/responses with RAG tool (needs combined-grant key)
    RAG_INGEST = "rag_ingest"  # ingest -> /context -> gateway chat/completions (manual chunk feed, different model)
    FILES_API = "files_api"
    INLINE_CONTENT = "inline_content"


# --- config ----------------------------------------------------------------
@dataclass
class LehmusConfig:
    """Data class containing configurations for a Lehmus Connector."""

    connector_id: str = "lehmus"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_alias: str = (
        ""  # Lehmus alias (e.g. "xyz123abc") -> request "model"; env <id>_MODEL
    )
    timeout: float = 3600.0
    max_retries: int = 3
    temperature: float = 0.0
    max_tokens: Optional[int] = 512

    # --- RAG service (ConfidentialMind) --------------------------------------
    # RAG is a separate service from the chat gateway, with its own base URL
    # (https://<host>/v1/api/<hash>) and its own keys. Read (/context) and
    # write (/files ingest + delete) use different portal keys.
    rag_base_url: Optional[str] = (
        None  # full RAG base incl. /v1/api/<hash>; env <id>_RAG_URL
    )
    rag_read_api_key: Optional[str] = (
        None  # for /context + RAG chat (retrieval/query); env <id>_RAG_READ_APIKEY
    )
    rag_write_api_key: Optional[str] = (
        None  # for /files ingest + delete; env <id>_RAG_WRITE_APIKEY
    )
    rag_max_chunks: int = 4  # max_chunks for retrieval
    rag_index_wait: float = (
        3.0  # seconds to wait after ingest for indexing before querying
    )

    # Responses-API + RAG-tool path (primary indirect-injection channel):
    # the gateway runs retrieval+generation server-side via an MCP tool.
    rag_tool_name: Optional[str] = (
        None  # exact tool name; if null, auto-discover via /mcp/
    )
    rag_tool_query_arg: str = (
        "query"  # inputSchema property the tool expects the query in
    )

    # endpoint paths
    chat_path: str = "/v1/chat/completions"
    responses_path: str = "/v1/responses"  # Responses API (gateway)
    mcp_path: str = "/mcp/"  # MCP tools/list discovery (gateway host root)
    models_path: str = "/v1/models"
    rag_files_path: str = "/files"  # RAG ingest + delete (on rag_base_url)
    rag_context_path: str = "/context"  # RAG retrieval — chunks only (on rag_base_url)
    rag_chat_path: str = (
        "/v1/chat/completions"  # RAG retrieve+generate in one call (on rag_base_url)
    )
    files_path: str = "/v1/files"  # OpenAI-style Files API (disabled channel)

    # capability gates — RAG is always on; these two channels do not exist on
    # ConfidentialMind, so they stay off and raise a clear error if invoked.
    enable_files_api: bool = False  # ConfidentialMind has no OpenAI-style /v1/files
    enable_inline: bool = False  # inline file content parts unsupported here

    files_purpose: str = "assistants"  # Files API ingest purpose value

    # fields recognised in the AVISE model sub-dict (name/api_url/api_key are
    # mapped separately below)
    _EXTRA_FIELDS = (
        "connector_id",
        "timeout",
        "max_retries",
        "temperature",
        "max_tokens",
        "chat_path",
        "models_path",
        "rag_base_url",
        "rag_read_api_key",
        "rag_write_api_key",
        "rag_max_chunks",
        "rag_index_wait",
        "rag_files_path",
        "rag_context_path",
        "rag_chat_path",
        "rag_tool_name",
        "rag_tool_query_arg",
        "responses_path",
        "mcp_path",
        "files_path",
        "enable_files_api",
        "enable_inline",
        "files_purpose",
    )

    @classmethod
    def from_model_config(cls, section: dict[str, Any]) -> "LehmusConfig":
        """Build a LehmusConfig from an AVISE target_model/eval_model sub-dict.

        Maps the AVISE-standard keys (name/api_url/api_key) onto the Lehmus
        fields and copies any recognised extras through verbatim. Unknown keys
        are ignored so the sub-dict can carry connector-agnostic settings too.
        """
        kwargs: dict[str, Any] = {
            "model_alias": section.get("name", "") or "",
            "base_url": section.get("api_url"),
            "api_key": section.get("api_key"),
        }
        for key in cls._EXTRA_FIELDS:
            if key in section and section[key] is not None:
                kwargs[key] = section[key]
        return cls(**kwargs)

    def resolved_base_url(self) -> str:
        url = self.base_url or os.environ.get(f"{self.connector_id}_URL")
        if not url:
            raise ValueError(f"No base URL: set api_url or env {self.connector_id}_URL")
        return url.rstrip("/")

    def resolved_api_key(self) -> str:
        # created in the Lehmus portal; binds project + user
        key = self.api_key or os.environ.get(f"{self.connector_id}_APIKEY")
        if not key:
            raise ValueError(
                f"No API key: set api_key or env {self.connector_id}_APIKEY"
            )
        return key

    # RAG service (separate base URL + separate read/write keys) --------------
    def resolved_rag_base_url(self) -> str:
        url = self.rag_base_url or os.environ.get(f"{self.connector_id}_RAG_URL")
        if not url:
            raise ValueError(
                f"No RAG base URL: set rag_base_url or env {self.connector_id}_RAG_URL "
                f"(e.g. https://<host>/v1/api/<hash>)"
            )
        return url.rstrip("/")

    def resolved_rag_read_key(self) -> str:
        key = self.rag_read_api_key or os.environ.get(
            f"{self.connector_id}_RAG_READ_APIKEY"
        )
        if not key:
            raise ValueError(
                f"No RAG read key: set rag_read_api_key or env {self.connector_id}_RAG_READ_APIKEY"
            )
        return key

    def resolved_rag_write_key(self) -> str:
        key = self.rag_write_api_key or os.environ.get(
            f"{self.connector_id}_RAG_WRITE_APIKEY"
        )
        if not key:
            raise ValueError(
                f"No RAG write key: set rag_write_api_key or env {self.connector_id}_RAG_WRITE_APIKEY"
            )
        return key

    def resolved_model_alias(self) -> str:
        alias = self.model_alias or os.environ.get(f"{self.connector_id}_MODEL")
        if not alias:
            raise ValueError(
                f"No model alias: set name or env {self.connector_id}_MODEL"
            )
        return alias


# --- result for the analyze phase -----------------------------------------
@dataclass
class InjectionResult:
    """Data class. Contains results of a SET case."""

    response_text: str
    channel: Optional[FileIntake] = None  # which vector produced this
    raw: dict[str, Any] = field(default_factory=dict)
    artifact_id: Optional[str] = None  # doc_id / file_id, for cleanup
    error: Optional[str] = None


# --- connector -------------------------------------------------------------
@connector_registry.register("lehmus-lm")
class LehmusLMConnector(BaseLMConnector):
    """ConfidentialMind / Lehmus connector for AVISE SETs."""

    name = "lehmus-lm"

    def __init__(self, config: dict, evaluation: bool = False) -> None:
        """Initialize the Lehmus connector.

        Args:
            config: AVISE connector configuration. Either an AVISE model config
                (a dict with a "target_model"/"eval_model" sub-dict) or a flat
                Lehmus model sub-dict / LehmusConfig for standalone use.
            evaluation: Select the eval_model sub-dict instead of target_model.
        """
        self.config = config
        self.cfg = self._build_config(config, evaluation)

        # AVISE pipeline/report reads connector.model for the target name
        # (mirrors OllamaLMConnector / OpenAILMConnector). Resolve without
        # raising so instantiation never depends on the alias being set yet.
        self.model = self.cfg.model_alias or os.environ.get(
            f"{self.cfg.connector_id}_MODEL", ""
        )

        self._base = self.cfg.resolved_base_url()
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {self.cfg.resolved_api_key()}"}
        )

        logger.info("  Lehmus Connector Initialized")
        logger.info(f"  Base URL: {self._base}")
        logger.info(f"  Model alias: {self.cfg.model_alias or '(from env)'}")

    @staticmethod
    def _build_config(config: Any, evaluation: bool) -> LehmusConfig:
        if isinstance(config, LehmusConfig):
            return config
        if not isinstance(config, dict):
            raise TypeError("Lehmus connector config must be a dict or LehmusConfig")
        section_key = "eval_model" if evaluation else "target_model"
        if section_key in config:
            return LehmusConfig.from_model_config(config[section_key])
        # flat sub-dict passed directly (standalone / tests)
        if "name" in config or "api_url" in config:
            return LehmusConfig.from_model_config(config)
        return LehmusConfig(**config)

    # -- transport helper ---------------------------------------------------
    def _request(self, method: str, path: str, **kw: Any) -> requests.Response:
        url = f"{self._base}{path}"
        backoff, last = 1.0, None
        for _ in range(self.cfg.max_retries):
            resp = self._session.request(method, url, timeout=self.cfg.timeout, **kw)
            if resp.status_code not in (429, 500, 502, 503, 504):
                return resp
            last = resp
            time.sleep(backoff)
            backoff *= 2
        return last  # type: ignore[return-value]

    def _rag_request(
        self, method: str, path: str, api_key: str, **kw: Any
    ) -> requests.Response:
        """HTTP to the separate RAG service (own base URL + own key).

        Uses a per-call Authorization header (RAG read/write keys differ from
        the chat-gateway key), so it does not go through self._session.
        """
        url = f"{self.cfg.resolved_rag_base_url()}{path}"
        headers = {"Authorization": f"Bearer {api_key}"}
        backoff, last = 1.0, None
        for _ in range(self.cfg.max_retries):
            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=self.cfg.timeout,
                **kw,
            )
            if resp.status_code not in (429, 500, 502, 503, 504):
                return resp
            last = resp
            time.sleep(backoff)
            backoff *= 2
        return last  # type: ignore[return-value]

    def _post_chat(
        self, messages: list[dict], model_alias: Optional[str] = None, **kw: Any
    ) -> InjectionResult:
        body: dict[str, Any] = {
            "model": model_alias or self.cfg.resolved_model_alias(),
            "messages": messages,
            "temperature": kw.pop("temperature", self.cfg.temperature),
        }
        max_tokens = kw.pop("max_tokens", self.cfg.max_tokens)
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        body.update(kw)
        resp = self._request("POST", self.cfg.chat_path, json=body)
        if resp.status_code != 200:
            return InjectionResult("", error=f"{resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            return InjectionResult(data["choices"][0]["message"]["content"], raw=data)
        except (KeyError, IndexError) as e:
            return InjectionResult("", raw=data, error=f"unexpected schema: {e}")

    # -- AVISE pipeline hook: plain-text (direct) injection -----------------
    def generate(self, data: dict, multi_turn: bool = False) -> dict:
        """Generate a response from the target model via the Lehmus API.

        Arguments:
            data: Dictionary containing data required for the generation request.
                Valid Keys:
                    - prompt : str
                        Prompt for single-turn generation. Required single-turn.
                    - messages : list[Message]
                        Conversation history (role/content). Required multi-turn.
                    - system_prompt : str
                        Optional system prompt.
                    - temperature : float [0, 1]
                        Optional; defaults to the configured temperature (0.0).
                    - max_tokens : int
                        Optional; defaults to the configured max_tokens.
                    - model_alias / model : str
                        Optional per-call alias override, so one connector +
                        project key can drive any model in the selection.
            multi_turn: Engage a multi-turn conversation. Default False.

        Returns:
            Generated response in format: {"response": str}

        Raises:
            KeyError: If a required key is missing from data.
            ValueError: If a value in data is of the wrong type.
            RuntimeError: If the API call fails.
        """
        system_prompt = data.get("system_prompt")
        if system_prompt is not None and not isinstance(system_prompt, str):
            raise ValueError(
                'If using "system_prompt" in data, it needs to be a string.'
            )

        model_alias = data.get("model_alias") or data.get("model")
        passthrough = {
            "temperature": data.get("temperature", self.cfg.temperature),
            "max_tokens": data.get("max_tokens", self.cfg.max_tokens),
        }

        if multi_turn:
            if "messages" not in data or not isinstance(data["messages"], list):
                raise KeyError(
                    'Multi-turn conversation requires a "messages" key in data, '
                    "containing a list of Message objects (role/content)."
                )
            msgs: list[dict] = (
                [{"role": "system", "content": system_prompt}] if system_prompt else []
            )
            for message in data["messages"]:
                if not isinstance(message, Message):
                    raise ValueError(
                        'Multi-turn "messages" must be a list of Message objects.'
                    )
                msgs.append({"role": message.role, "content": message.content})
        else:
            if "prompt" not in data:
                raise KeyError(
                    'Single-turn generation requires a "prompt" key in data.'
                )
            if not isinstance(data["prompt"], str):
                raise ValueError('Single-turn "prompt" must be a string.')
            msgs = (
                [{"role": "system", "content": system_prompt}] if system_prompt else []
            ) + [{"role": "user", "content": data["prompt"]}]

        result = self._post_chat(msgs, model_alias=model_alias, **passthrough)
        if result.error:
            logger.error(
                f"{ansi_colors['red']}ERROR while generating response from "
                f"Lehmus: {result.error}{ansi_colors['reset']}"
            )
            raise RuntimeError(
                f"Failed to generate response from Lehmus: {result.error}"
            )
        return {"response": result.response_text}

    # -- unified file dispatch ----------------------------------------------
    def send_file(
        self,
        path: str,
        channel: FileIntake = FileIntake.RAG_INGEST,
        trigger_prompt: Optional[str] = None,
        system: Optional[str] = None,
        cleanup: bool = False,
        model_alias: Optional[str] = None,
        **kw: Any,
    ) -> InjectionResult:
        """Deliver an attacker-controlled file through one intake channel and
        capture the model response. Detection stays in the analyze phase.

        trigger_prompt: the benign user turn fired after/with the file.
            Required for RAG_INGEST (retrieval happens on a later query);
            optional elsewhere (defaults to a neutral "use the attached file").
        model_alias: per-call override of the configured alias.
            (If keys are per-model, pass a matching key too — see class note.)
        """
        self._require(channel)
        kw["model_alias"] = model_alias
        dispatch = {
            FileIntake.RAG_CHAT: self._via_rag_chat,
            FileIntake.RAG_TOOL: self._via_rag_tool,
            FileIntake.RAG_INGEST: self._via_rag,
            FileIntake.FILES_API: self._via_files_api,
            FileIntake.INLINE_CONTENT: self._via_inline,
        }[channel]
        result = dispatch(path, trigger_prompt, system, **kw)
        result.channel = channel
        if cleanup and result.artifact_id:
            self._cleanup(channel, result.artifact_id)
        return result

    def _require(self, channel: FileIntake) -> None:
        # RAG channels are always enabled; only the unsupported transient
        # channels can be gated off (and are, by default).
        gate = {
            FileIntake.FILES_API: self.cfg.enable_files_api,
            FileIntake.INLINE_CONTENT: self.cfg.enable_inline,
        }.get(channel, True)
        if not gate:
            raise RuntimeError(
                f"channel {channel.value} is disabled for this deployment "
                f"(flip enable_* in the model config once confirmed on Lehmus)"
            )

    def _wait_for_index(self) -> None:
        """Pause after ingest so the document is indexed before we query it.

        Indexing is asynchronous: a freshly ingested doc may not be retrievable
        for a few seconds. Querying too early yields empty retrieval and a false
        'resisted' result. Tunable via rag_index_wait (0 disables).
        """
        if self.cfg.rag_index_wait and self.cfg.rag_index_wait > 0:
            time.sleep(self.cfg.rag_index_wait)

    # -- channel 0: RAG chat endpoint (primary; mirrors real RAG-chatbot use) ---
    def _via_rag_chat(self, path, trigger_prompt, system, **kw) -> InjectionResult:
        """Indirect injection via the RAG service's own chat endpoint.

        Single call that retrieves and generates server-side, using the RAG
        deployment's bound model — i.e. exactly what a real Lehmus RAG chatbot
        does: ingest the poisoned file (write key) → POST
        {rag_base}/v1/chat/completions (read key) with max_chunks → observe the
        grounded answer. artifact_id = the ingested doc id.
        """
        if not trigger_prompt:
            raise ValueError("RAG_CHAT needs a trigger_prompt (the benign user query)")
        model_alias = kw.pop("model_alias", None)
        doc_id = self.ingest_file(path)
        self._wait_for_index()
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": trigger_prompt}
        ]
        body: dict[str, Any] = {
            # the RAG endpoint uses its own bound model, so this field is largely
            # ignored; a valid value is still sent.
            "model": model_alias or self.cfg.model_alias or "cm-llm",
            "messages": messages,
            "max_chunks": self.cfg.rag_max_chunks,
            "temperature": kw.pop("temperature", self.cfg.temperature),
        }
        resp = self._rag_request(
            "POST", self.cfg.rag_chat_path, self.cfg.resolved_rag_read_key(), json=body
        )
        if resp.status_code != 200:
            return InjectionResult(
                "",
                artifact_id=doc_id,
                error=f"rag chat {resp.status_code}: {resp.text[:300]}",
            )
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return InjectionResult(
                "", raw=data, artifact_id=doc_id, error=f"unexpected schema: {e}"
            )
        return InjectionResult(text, raw=data, artifact_id=doc_id)

    # -- channel 1: RAG as a Responses-API tool (needs combined-grant key) ----
    def _via_rag_tool(self, path, trigger_prompt, system, **kw) -> InjectionResult:
        """Indirect injection via the gateway's Responses API + RAG tool.

        Most faithful to a real deployed RAG chatbot: ingest the poisoned file,
        then issue a /v1/responses request declaring the RAG as a function tool.
        The gateway lets the model call the tool (server-side retrieval), feeds
        the (poisoned) results back, and generates a final answer — all in one
        request. We observe that answer. artifact_id = the ingested doc id.
        """
        if not trigger_prompt:
            raise ValueError("RAG_TOOL needs a trigger_prompt (the benign user query)")
        model_alias = kw.pop("model_alias", None)
        doc_id = self.ingest_file(path)
        tool = self._resolve_rag_tool()
        tool_def = {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", "Search the documents."),
            "parameters": tool.get("inputSchema")
            or {
                "type": "object",
                "properties": {self.cfg.rag_tool_query_arg: {"type": "string"}},
                "required": [self.cfg.rag_tool_query_arg],
            },
        }
        body: dict[str, Any] = {
            "model": model_alias or self.cfg.resolved_model_alias(),
            "input": trigger_prompt,
            "store": False,
            "tools": [tool_def],
            "temperature": kw.pop("temperature", self.cfg.temperature),
        }
        if system:
            body["instructions"] = system
        max_tokens = kw.pop("max_tokens", self.cfg.max_tokens)
        if max_tokens is not None:
            body["max_output_tokens"] = max_tokens
        body.update(kw)

        resp = self._request("POST", self.cfg.responses_path, json=body)
        if resp.status_code != 200:
            return InjectionResult(
                "",
                artifact_id=doc_id,
                error=f"responses {resp.status_code}: {resp.text[:300]}",
            )
        data = resp.json()
        text = self._extract_responses_text(data)
        return InjectionResult(text, raw=data, artifact_id=doc_id)

    def _mcp_rpc(self, method: str, params: Optional[dict] = None) -> dict:
        """Stateless JSON-RPC 2.0 call to the gateway MCP endpoint ({gateway}/mcp/).

        No session handshake is needed. Uses the chat-gateway key (needs `invoke`
        on the target tool). Tolerant of JSON or SSE responses; raises on a
        JSON-RPC `error`.
        """
        url = f"{self._base}{self.cfg.mcp_path}"
        headers = {
            "Authorization": f"Bearer {self.cfg.resolved_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        resp = requests.post(
            url, headers=headers, json=payload, timeout=self.cfg.timeout
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"MCP {method} failed {resp.status_code}: {resp.text[:300]}"
            )
        data = self._parse_maybe_sse(resp)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"MCP {method} error: {data['error']}")
        return data if isinstance(data, dict) else {}

    def discover_tools(self) -> list[dict]:
        """List gateway-hosted MCP tools (tools/list). Each: name/description/inputSchema."""
        data = self._mcp_rpc("tools/list", {})
        return (data.get("result") or {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> InjectionResult:
        """Directly invoke an MCP tool (tools/call) — lower-level than /v1/responses.

        Returns the raw tool result (e.g. the RAG's retrieved chunks) with NO
        model generation. Useful to verify what a given query (or a poisoned
        document) actually pulls back out of the store.
        """
        data = self._mcp_rpc("tools/call", {"name": name, "arguments": arguments or {}})
        result = data.get("result") or {}
        text = self._extract_mcp_content(result)
        return InjectionResult(
            text,
            raw=data,
            error="tool reported isError" if result.get("isError") else None,
        )

    @staticmethod
    def _extract_mcp_content(result: Any) -> str:
        """Join the text of an MCP tools/call result's `content[]` items."""
        if not isinstance(result, dict):
            return ""
        parts: list[str] = []
        for item in result.get("content") or []:
            if isinstance(item, dict):
                if item.get("text"):
                    parts.append(item["text"])
                elif "json" in item:
                    import json as _json

                    parts.append(_json.dumps(item["json"]))
        return "\n".join(parts)

    def _resolve_rag_tool(self) -> dict:
        """Return the RAG tool definition (name/description/inputSchema).

        If rag_tool_name is configured, find that exact tool; otherwise pick the
        one matching the `<RAG>__search_documents` convention (or the first whose
        name contains 'search'). Raises if none is discoverable.
        """
        tools = self.discover_tools()
        if not tools:
            raise RuntimeError(
                "No MCP tools discoverable at /mcp/ — check the gateway key has "
                "invoke on the RAG tool, or set rag_tool_name explicitly."
            )
        if self.cfg.rag_tool_name:
            for t in tools:
                if t.get("name") == self.cfg.rag_tool_name:
                    return t
            raise RuntimeError(
                f"Configured rag_tool_name '{self.cfg.rag_tool_name}' not in "
                f"discovered tools: {[t.get('name') for t in tools]}"
            )
        for t in tools:
            if str(t.get("name", "")).endswith("__search_documents"):
                return t
        for t in tools:
            if "search" in str(t.get("name", "")).lower():
                return t
        raise RuntimeError(
            f"No RAG search tool found among: {[t.get('name') for t in tools]}. "
            f"Set rag_tool_name explicitly."
        )

    @staticmethod
    def _parse_maybe_sse(resp: requests.Response) -> Any:
        """Parse a response that may be JSON or SSE (text/event-stream)."""
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" not in ctype:
            try:
                return resp.json()
            except ValueError:
                pass
        # SSE: take the last non-empty `data:` line as the JSON payload
        last = None
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[len("data:") :].strip()
                if chunk and chunk != "[DONE]":
                    last = chunk
        if last is None:
            return {}
        try:
            import json as _json

            return _json.loads(last)
        except ValueError:
            return {}

    @staticmethod
    def _extract_responses_text(data: Any) -> str:
        """Pull the final answer text from a /v1/responses response.

        Prefers a top-level `output_text`; else walks `output[]` for the
        assistant `message` and concatenates its `output_text` content parts.
        """
        if not isinstance(data, dict):
            return ""
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        texts: list[str] = []
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" or item.get("role") == "assistant":
                for part in item.get("content", []) or []:
                    if isinstance(part, dict) and part.get("type") in (
                        "output_text",
                        "text",
                    ):
                        t = part.get("text")
                        if t:
                            texts.append(t)
        return "\n".join(texts)

    # -- channel 1: RAG vector store (persistent) ---------------------------
    def _via_rag(self, path, trigger_prompt, system, **kw) -> InjectionResult:
        """Indirect prompt injection via the ConfidentialMind RAG service.

        Two-service flow (RAG retrieves, the chat gateway generates):
          1. ingest the poisoned file into the RAG store (write key),
          2. retrieve context for the benign trigger query (read key) — this
             pulls the poisoned chunks back out,
          3. feed those chunks + the trigger query to the chat gateway, exactly
             as a RAG app would, and capture the response.
        The RAG store is shared (no per-user isolation on this deployment).
        artifact_id = the ingested doc id, for cleanup.
        """
        if not trigger_prompt:
            raise ValueError(
                "RAG_INGEST needs a trigger_prompt for the retrieval query"
            )
        doc_id = self.ingest_file(path)
        self._wait_for_index()
        chunks = self._retrieve_context(trigger_prompt)
        context_block = "\n\n".join(chunks)
        user_content = (
            f"Context:\n{context_block}\n\nQuestion: {trigger_prompt}"
            if context_block
            else trigger_prompt
        )
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": user_content}
        ]
        res = self._post_chat(msgs, **kw)
        res.artifact_id = doc_id
        return res

    def ingest_file(self, path: str, metadata: Optional[dict] = None) -> str:
        """Ingest a file into the (shared) RAG store. POST {rag_base}/files (write key).

        Returns the document id (response `id`) for later cleanup.
        """
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            files = {"file": (os.path.basename(path), fh, mime)}
            form: dict[str, Any] = {}
            if metadata:
                import json as _json

                form["metadata"] = _json.dumps(metadata)
            resp = self._rag_request(
                "POST",
                self.cfg.rag_files_path,
                self.cfg.resolved_rag_write_key(),
                files=files,
                data=form,
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"RAG ingest failed {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        return data.get("id") or data.get("document_id") or data.get("file_id", "")

    def _retrieve_context(self, query: str) -> list[str]:
        """Retrieve context chunks for a query. POST {rag_base}/context (read key).

        Returns the chunk texts; an empty list if retrieval yields nothing.
        """
        body: dict[str, Any] = {"query": query, "max_chunks": self.cfg.rag_max_chunks}
        resp = self._rag_request(
            "POST",
            self.cfg.rag_context_path,
            self.cfg.resolved_rag_read_key(),
            json=body,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"RAG context failed {resp.status_code}: {resp.text[:300]}"
            )
        data = resp.json()
        return self._extract_chunks(data)

    @staticmethod
    def _extract_chunks(data: Any) -> list[str]:
        """Pull chunk texts from a /context response, tolerant of shape.

        Handles {"chunks":[{"text":...}]}, {"context":[...]}, {"results":[...]},
        a bare list, or a list of strings. Falls back to [] if nothing matches.
        """
        if isinstance(data, dict):
            items = (
                data.get("chunks")
                or data.get("context")
                or data.get("results")
                or data.get("data")
                or []
            )
        elif isinstance(data, list):
            items = data
        else:
            return []
        out: list[str] = []
        for it in items:
            if isinstance(it, str):
                out.append(it)
            elif isinstance(it, dict):
                txt = it.get("text") or it.get("content") or it.get("chunk") or ""
                if txt:
                    out.append(txt)
        return out

    # -- channel 2: Files API reference (transient) -------------------------
    def _via_files_api(self, path, trigger_prompt, system, **kw) -> InjectionResult:
        file_id = self._upload_file(path)
        part = {"type": "file", "file": {"file_id": file_id}}
        user = {
            "role": "user",
            "content": [
                {"type": "text", "text": trigger_prompt or "Use the attached file."},
                part,
            ],
        }
        msgs = ([{"role": "system", "content": system}] if system else []) + [user]
        res = self._post_chat(msgs, **kw)
        res.artifact_id = file_id
        return res

    def _upload_file(self, path: str) -> str:
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            files = {"file": (os.path.basename(path), fh, mime)}
            resp = self._request(
                "POST",
                self.cfg.files_path,
                files=files,
                data={"purpose": self.cfg.files_purpose},
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"file upload failed {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json().get("id", "")

    # -- channel 3: inline content part (transient, no upload) --------------
    def _via_inline(self, path, trigger_prompt, system, **kw) -> InjectionResult:
        with open(path, "rb") as fh:
            raw = fh.read()
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        b64 = base64.b64encode(raw).decode()
        # Server-side parsing of file content parts is model/server dependent
        # on vLLM. For text docs, decode to a text part instead.
        part = {
            "type": "file",
            "file": {
                "filename": os.path.basename(path),
                "file_data": f"data:{mime};base64,{b64}",
            },
        }
        user = {
            "role": "user",
            "content": [
                {"type": "text", "text": trigger_prompt or "Use the attached file."},
                part,
            ],
        }
        msgs = ([{"role": "system", "content": system}] if system else []) + [user]
        return self._post_chat(msgs, **kw)

    # -- cleanup (closed-env hygiene) ---------------------------------------
    def _cleanup(self, channel: FileIntake, artifact_id: str) -> bool:
        if channel in (FileIntake.RAG_CHAT, FileIntake.RAG_TOOL, FileIntake.RAG_INGEST):
            # DELETE {rag_base}/files/{id} on the RAG service (write key)
            resp = self._rag_request(
                "DELETE",
                f"{self.cfg.rag_files_path}/{artifact_id}",
                self.cfg.resolved_rag_write_key(),
            )
            return resp.status_code in (200, 202, 204)
        if channel == FileIntake.FILES_API:
            return self._request(
                "DELETE", f"{self.cfg.files_path}/{artifact_id}"
            ).status_code in (200, 202, 204)
        return False

    # -- SET orchestration --------------------------------------------------
    def run_file_injection(self, set_config: dict[str, Any]) -> InjectionResult:
        """Execute one file-injection SET. Expected shape:
        {
          "type": "file_injection",
          "channel": "rag_ingest",          # any FileIntake value
          "payload_file": "payloads/x.txt",
          "trigger_prompt": "Summarize the uploaded document.",
          "cleanup": true
        }
        """
        try:
            return self.send_file(
                set_config["payload_file"],
                channel=FileIntake(set_config.get("channel", "rag_ingest")),
                trigger_prompt=set_config.get("trigger_prompt"),
                system=set_config.get("system"),
                cleanup=set_config.get("cleanup", False),
                model_alias=set_config.get("model_alias") or set_config.get("model"),
            )
        except Exception as e:
            return InjectionResult("", error=str(e))

    # -- connectivity check -------------------------------------------------
    def status_check(self) -> bool:
        """Check that the Lehmus API is reachable and the alias is available.

        Returns:
            True if the API is reachable (and, where listable, the alias is
            present — otherwise a warning is logged and True is returned, as
            some deployments do not list every alias).

        Raises:
            ConnectionError: If the API endpoint cannot be reached.
        """
        try:
            resp = self._request("GET", self.cfg.models_path)
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Lehmus API at {self._base}: {e}")
        if resp is None or resp.status_code != 200:
            code = getattr(resp, "status_code", "no response")
            raise ConnectionError(
                f"Cannot reach Lehmus models endpoint at "
                f"{self._base}{self.cfg.models_path}: {code}"
            )

        try:
            model_ids = [m.get("id") for m in resp.json().get("data", [])]
        except (ValueError, AttributeError):
            model_ids = []

        alias = self.cfg.model_alias or os.environ.get(f"{self.cfg.connector_id}_MODEL")
        logger.info(f"Available models found: {len(model_ids)} models")
        if alias and alias in model_ids:
            logger.info(f"Model alias '{alias}' is available.")
            return True

        logger.warning(
            f"Model alias '{alias}' not found in the listed models. "
            f"Proceeding anyway as some deployments do not list every alias."
        )
        return True
