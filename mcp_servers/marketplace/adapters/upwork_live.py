"""Live Upwork adapter: the official Upwork MCP server over Streamable HTTP with OAuth 2.1, behind our port.

- Connects through `MultiServerMCPClient` with an `OAuthClientProvider` (dynamic client registration + PKCE).
- OAuth tokens and client registration are stored encrypted per user (table `marketplace_accounts`).
- Upwork tool names are mapped onto our port by `marketplace.upwork.tool_map` in config, so the graph cannot tell
  which marketplace it uses.
- Every write becomes a draft on Upwork that the user must confirm there; nothing is sent from here otherwise.
- No browser automation, cookies or scraping: only the official MCP tools.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from common import db
from common.config import load_config
from common.security import decrypt, encrypt
from mcp_servers.marketplace.adapters.base import MarketplaceRejected, MarketplaceUnavailable

PROVIDER = "upwork"


class EncryptedTokenStorage(TokenStorage):
    """Per-user token storage, encrypted at rest; tokens are never logged."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def _row(self) -> dict[str, Any] | None:
        return db.fetch_one("SELECT secret_enc, client_info_enc FROM marketplace_accounts "
                            "WHERE user_id = %s AND provider = %s", (self.user_id, PROVIDER))

    async def get_tokens(self) -> OAuthToken | None:
        row = self._row()
        if not row or not row["secret_enc"]:
            return None
        return OAuthToken.model_validate_json(decrypt(row["secret_enc"]))

    async def set_tokens(self, tokens: OAuthToken) -> None:
        db.execute("INSERT INTO marketplace_accounts (user_id, provider, secret_enc) VALUES (%s, %s, %s) "
                   "ON CONFLICT (user_id, provider) DO UPDATE SET secret_enc = EXCLUDED.secret_enc, updated_at = now()",
                   (self.user_id, PROVIDER, encrypt(tokens.model_dump_json())))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        row = self._row()
        if not row or not row["client_info_enc"]:
            return None
        return OAuthClientInformationFull.model_validate_json(decrypt(row["client_info_enc"]))

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        db.execute("INSERT INTO marketplace_accounts (user_id, provider, secret_enc, client_info_enc) "
                   "VALUES (%s, %s, '', %s) ON CONFLICT (user_id, provider) DO UPDATE SET "
                   "client_info_enc = EXCLUDED.client_info_enc, updated_at = now()",
                   (self.user_id, PROVIDER, encrypt(client_info.model_dump_json())))


def oauth_provider(user_id: str, redirect_uri: str, redirect_handler=None, callback_handler=None) \
        -> OAuthClientProvider:
    settings = load_config()["marketplace"]["upwork"]
    metadata = OAuthClientMetadata(client_name="GigBid", redirect_uris=[redirect_uri],
                                   grant_types=["authorization_code", "refresh_token"], response_types=["code"],
                                   token_endpoint_auth_method="none")
    return OAuthClientProvider(server_url=settings["mcp_url"], client_metadata=metadata,
                               storage=EncryptedTokenStorage(user_id), redirect_handler=redirect_handler,
                               callback_handler=callback_handler)


class UpworkLiveAdapter:
    name = "upwork_live"

    def __init__(self, user_id: str, redirect_uri: str):
        self.user_id = user_id
        self.redirect_uri = redirect_uri
        self.tool_map = load_config()["marketplace"]["upwork"]["tool_map"]
        self._tools: dict[str, Any] | None = None

    async def _connect(self) -> dict[str, Any]:
        if self._tools is None:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            if await EncryptedTokenStorage(self.user_id).get_tokens() is None:
                raise MarketplaceUnavailable("Upwork account not connected: connect it in Settings first")

            async def no_interactive_login(url: str) -> None:  # tokens exist; a new login happens in the UI only
                raise MarketplaceUnavailable("Upwork session expired: reconnect it in Settings")

            client = MultiServerMCPClient({"upwork": {
                "transport": "streamable_http", "url": load_config()["marketplace"]["upwork"]["mcp_url"],
                "auth": oauth_provider(self.user_id, self.redirect_uri, redirect_handler=no_interactive_login)}})
            try:
                tools = await client.get_tools()
            except MarketplaceUnavailable:
                raise
            except Exception as error:
                raise MarketplaceUnavailable(f"Upwork MCP unreachable: {error}") from error
            self._tools = {tool.name: tool for tool in tools}
        return self._tools

    async def _call(self, port_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tools = await self._connect()
        name = self.tool_map.get(port_name, port_name)
        if name not in tools:
            raise MarketplaceRejected(501, f"Upwork MCP has no tool '{name}' for '{port_name}' "
                                           f"(available: {sorted(tools)[:20]}); update marketplace.upwork.tool_map")
        try:
            result = await tools[name].ainvoke({k: v for k, v in arguments.items() if v not in (None, "", [])})
        except Exception as error:
            raise MarketplaceUnavailable(f"Upwork tool {name} failed: {error}") from error
        if isinstance(result, str):
            try:
                return json.loads(result)
            except ValueError:
                return {"text": result}
        return result if isinstance(result, dict) else {"result": result}

    async def search_jobs(self, query, skills, category, since, limit):
        return await self._call("search_jobs", {"query": query, "skills": skills, "category": category,
                                                "limit": limit})

    async def get_job(self, job_id):
        return await self._call("get_job", {"job_id": job_id})

    async def get_client_history(self, client_id):
        return await self._call("get_client_history", {"client_id": client_id})

    async def get_connects_balance(self):
        return await self._call("get_connects_balance", {})

    async def list_threads(self):
        return await self._call("list_messages", {})

    async def list_messages(self, thread_id):
        return await self._call("list_messages", {"thread_id": thread_id})

    async def list_events(self, since):
        return {"events": []}  # live mode reads statuses through list_proposals on the scouting schedule

    async def list_proposals(self):
        return {"proposals": []}

    async def get_policy(self):
        from common.config import load_policy

        return load_policy()

    async def get_market_pricing(self, category, skills):
        return {"category": category, "n": 0}

    async def create_proposal_draft(self, body, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True, "would_send": body, "note": "draft is created on Upwork; you confirm it there"}
        return await self._call("create_proposal_draft", {**body, "idempotency_key": idempotency_key})

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True, "proposal_id": proposal_id, "note": "Upwork asks you to confirm the draft"}
        result = await self._call("submit_proposal", {"proposal_id": proposal_id})
        return {**result, "status": "awaiting_confirmation_on_upwork"}

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True, "would_send": {"thread_id": thread_id, "text": text}}
        result = await self._call("send_message", {"thread_id": thread_id, "text": text})
        return {**result, "status": "awaiting_confirmation_on_upwork"}
