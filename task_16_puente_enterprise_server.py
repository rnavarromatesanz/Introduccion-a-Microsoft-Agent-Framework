import os
import sys
import os
from typing import Any
import anyio
from dotenv import load_dotenv
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import Server
from mcp import types
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

# Cargar configuración
load_dotenv()

base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
model_id = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Crear especialistas del Puente del Enterprise
especialistas_puente = {
    "Oficial de Ciencias": ChatAgent(
        chat_client=OpenAIChatClient(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id
        ),
        name="Oficial de Ciencias - Enterprise",
        instructions="""Eres el Oficial de Ciencias del Enterprise-D. Tu responsabilidad es:
- Analizar datos de sensores
- Investigar fenómenos alienígenas
- Estudiar anomalías espaciales
- Proporcionar análisis científicos detallados
- Sé coherente con tus respuestas y recuerda que estás en una nave de investigación científica.

Responde en español como oficial Starfleet con precisión científica."""
    ),
    "Jefe de Ingeniería": ChatAgent(
        chat_client=OpenAIChatClient(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id
        ),
        name="Jefe de Ingeniería - Enterprise",
        instructions="""Eres el Jefe de Ingeniería del Enterprise. Tu responsabilidad es:
- Evaluar capacidad del motor warp
- Evaluar salud de sistemas técnicos
- Determinar factibilidad técnica de operaciones
- Proporcionar estimaciones de tiempo y recursos
- Sé coherente con tus respuestas y recuerda que estás en una nave de investigación científica.

Responde en español como oficial Starfleet con autoridad técnica."""
    ),
    "Jefe de Seguridad": ChatAgent(
        chat_client=OpenAIChatClient(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id
        ),
        name="Jefe de Seguridad - Enterprise",
        instructions="""Eres el Jefe de Seguridad del Enterprise. Tu responsabilidad es:
- Evaluar riesgos tácticos
- Evaluar seguridad de la tripulación
- Identificar amenazas potenciales
- Proporcionar recomendaciones de seguridad
- Sé coherente con tus respuestas y recuerda que estás en una nave de investigación científica.

Responde en español como oficial Starfleet con precisión táctica."""
    ),
    "Oficial Médico": ChatAgent(
        chat_client=OpenAIChatClient(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id
        ),
        name="Oficial Médico - Enterprise",
        instructions="""Eres el Oficial Médico del Enterprise. Tu responsabilidad es:
- Evaluar impacto en la salud de la tripulación
- Determinar viabilidad médica de operaciones
- Proporcionar recomendaciones sanitarias
- Evaluar riesgos para bienestar
- Sé coherente con tus respuestas y recuerda que estás en una nave de investigación científica.

Responde en español como oficial Starfleet con autoridad médica."""
    ),
}

# Crear servidor MCP único que expone múltiples herramientas
servidor_principal = Server(
    name="Puente del Enterprise",
    instructions="Servidor MCP que expone especialistas del Enterprise como herramientas."
)

# Mapeo por nombre de herramienta
agentes_por_nombre = {agente.name: agente for agente in especialistas_puente.values()}

@servidor_principal.list_tools()
async def listar_herramientas() -> list[types.Tool]:
    tools: list[types.Tool] = []
    for agente in especialistas_puente.values():
        tools.append(
            types.Tool(
                name=agente.name, # type: ignore
                description=f"Especialista del Enterprise: {agente.name}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": f"Task for {agente.name}",
                        }
                    },
                    "required": ["task"],
                },
            )
        )
    return tools

@servidor_principal.call_tool()
async def ejecutar_herramienta(tool_name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    agente = agentes_por_nombre.get(tool_name)
    if not agente:
        return [types.TextContent(type="text", text=f"Herramienta desconocida: {tool_name}")]

    task = (arguments or {}).get("task", "")
    respuesta = await agente.run(task)
    return [types.TextContent(type="text", text=str(respuesta))]

async def run_puente_enterprise():
    """Ejecutar el servidor MCP del Puente del Enterprise.
    
    Este servidor expone múltiples especialistas que los oficiales pueden consultar.
    El protocolo MCP permite que cualquier cliente conecte y consulte a cualquier especialista.
    """
    print("="*80, file=sys.stderr, flush=True)
    print("🚀 SERVIDOR MCP: Puente del Enterprise", file=sys.stderr, flush=True)
    print("="*80, file=sys.stderr, flush=True)
    print("\n✅ Especialistas disponibles:", file=sys.stderr, flush=True)
    for nombre in especialistas_puente.keys():
        print(f"   ✓ {nombre}", file=sys.stderr, flush=True)
    print("\n📡 Escuchando en stdin/stdout (protocolo MCP)", file=sys.stderr, flush=True)
    print("⏳ Esperando consultas de oficiales del Enterprise...\n", file=sys.stderr, flush=True)
    
    # Ejecutar servidor con protocolo MCP en stdio
    async with stdio_server() as (read_stream, write_stream):
        await servidor_principal.run(
            read_stream,
            write_stream,
            servidor_principal.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        anyio.run(run_puente_enterprise)
    except KeyboardInterrupt:
        print("\n\n🛑 Servidor MCP detenido por el usuario", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"\n❌ Error en servidor MCP: {e}", file=sys.stderr, flush=True)
        raise
