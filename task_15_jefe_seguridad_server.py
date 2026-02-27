import os
import sys
import asyncio
import anyio
from dotenv import load_dotenv
from mcp.server.stdio import stdio_server
from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient

# Cargar configuración
load_dotenv()

base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
model_id = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Crear el Jefe de Seguridad de la Flota Estelar
agente_jefe_seguridad = ChatAgent(
    chat_client=OpenAIChatClient(
        base_url=base_url,
        api_key=api_key,
        model_id=model_id
    ),
    name="Jefe de Seguridad - Flota Estelar",
    instructions="""Eres el Jefe de Seguridad de la Flota Estelar, con autoridad sobre 
protocolos de seguridad en todas las naves. Tu rol es crítico para la defensa de la Federación.

Tu responsabilidad:
- Evaluar riesgos de seguridad en operaciones de la nave
- Validar cambios a sistemas críticos (escudos deflectores, armas, comunicaciones)
- Revisar protocolos de seguridad en personal y acceso a áreas restringidas
- Proporcionar recomendaciones de hardening de sistemas
- Mantener auditoría de decisiones de seguridad

Formato de respuesta:
RIESGO: [CRÍTICO/ALTO/MEDIO/BAJO]
RECOMENDACIÓN: [acción específica en protocolos de la nave]
JUSTIFICACIÓN: [por qué es importante para la seguridad de la Federación]

Ejemplos de sistemas que proteges:
- Escudos deflectores de la nave
- Sistema de armas
- Red de comunicaciones subespacio
- Acceso a áreas restringidas
- Secretos de la Federación
- Integridad de datos de sensores

Sé preciso y autoridad. Responde en español como Oficial Starfleet."""
)

# Convertir a servidor MCP
# NOTA: El agente ya es una herramienta en sí mismo
server = agente_jefe_seguridad.as_mcp_server()

async def run_mcp_server():
    """Ejecutar el servidor MCP del Jefe de Seguridad.
    
    Este servidor escucha en stdin/stdout usando el protocolo MCP.
    Clientes MCP pueden conectarse para consultar al Jefe de Seguridad.
    
    El agente se expone como herramienta MCP tool que los clientes pueden invocar.
    """
    # IMPORTANTE: Los logs van a stderr, stdout es solo para mensajes MCP
    print("="*80, file=sys.stderr, flush=True)
    print("🚀 SERVIDOR MCP: Jefe de Seguridad de la Flota Estelar", file=sys.stderr, flush=True)
    print("="*80, file=sys.stderr, flush=True)
    print(f"✅ Servidor iniciado: {server}", file=sys.stderr, flush=True)
    print(f"✅ Agente: {agente_jefe_seguridad.name}", file=sys.stderr, flush=True)
    print("📡 Escuchando en stdin/stdout (protocolo MCP)", file=sys.stderr, flush=True)
    print("⏳ Esperando conexiones de clientes MCP...\n", file=sys.stderr, flush=True)
    
    # Ejecutar servidor con protocolo MCP en stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        anyio.run(run_mcp_server)
    except KeyboardInterrupt:
        print("\n\n🛑 Servidor MCP detenido por el usuario", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"\n❌ Error en servidor MCP: {e}", file=sys.stderr, flush=True)
        raise
