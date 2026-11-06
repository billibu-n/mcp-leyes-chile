"""Cliente MCP real por stdio: mismo camino que usaria un host."""
from __future__ import annotations

import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class Cliente:
    def __init__(self, comando: str = "mcp-leyes-chile", args: tuple = (), env: dict | None = None):
        # stdio_client filtra el entorno del host: sin esto, MCP_LEYES_DB no llega al servidor.
        self.params = StdioServerParameters(command=comando, args=list(args),
                                            env=dict(os.environ) if env is None else env)

    async def __aenter__(self):
        self._cm = stdio_client(self.params)
        self.read, self.write = await self._cm.__aenter__()
        self.session = ClientSession(self.read, self.write)
        await self.session.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.session.__aexit__(*exc)
        await self._cm.__aexit__(*exc)

    async def tools(self) -> list[str]:
        return [t.name for t in (await self.session.list_tools()).tools]

    async def llamar(self, nombre: str, args: dict) -> dict:
        r = await self.session.call_tool(nombre, args)
        texto = r.content[0].text if getattr(r, "content", None) else "{}"
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return {"_crudo": texto}
