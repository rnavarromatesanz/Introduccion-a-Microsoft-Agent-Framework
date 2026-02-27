import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def consultar_jefe_seguridad():
    """Cliente que se conecta al servidor MCP del Jefe de Seguridad.
    
    Este cliente se conecta al servidor jefe_seguridad_server.py via MCP.
    El Oficial de Operaciones consulta al Jefe de Seguridad sobre decisiones críticas.
    """
    
    print("="*80)
    print("🚀 CLIENTE MCP: Oficial de Operaciones - Enterprise")
    print("="*80)
    print("\n📡 Conectando al servidor MCP del Jefe de Seguridad...")
    
    # Parámetros para conectar al servidor
    server_params = StdioServerParameters(
        command="python",
        args=["task_15_jefe_seguridad_server.py"],
        env=None
    )
    
    try:
        # Conectar al servidor MCP
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                
                # Inicializar sesión MCP
                await session.initialize()
                
                print("✅ Conexión establecida con Jefe de Seguridad (servidor MCP)\n")
                
                # Listar herramientas disponibles del servidor
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"🔧 Herramientas disponibles: {tool_names}\n")
                
                if not tool_names:
                    print("⚠️  No hay herramientas disponibles en el servidor")
                    return
                    
                # Consulta del Oficial de Operaciones sobre cambio crítico
                cambio = """Necesito expandir acceso a sala de máquinas del Enterprise.
                        El Ingeniero Jefe necesita que 5 técnicos adicionales tengan acceso a sistemas
                        de warp drive para mantenimiento. ¿Es seguro autorizar esto?"""
                
                print(f"🔄 Oficial de Operaciones pregunta:\n{cambio}\n")
                
                # Usar la primera herramienta disponible (el agente mismo)
                tool_name = tool_names[0]
                print(f"📞 Llamando a herramienta: {tool_name}\n")
                
                # Llamar al servidor MCP con el argumento correcto: "task"
                resultado = await session.call_tool(
                    name=tool_name,
                    arguments={"task": cambio}  # El schema requiere "task"
                )
                
                # El resultado puede ser una lista de contenido
                if hasattr(resultado, 'content') and resultado.content:
                    respuesta = resultado.content[0].text if isinstance(resultado.content, list) else resultado.content # type: ignore
                else:
                    respuesta = str(resultado)
                
                print(f"✅ Jefe de Seguridad (via MCP) responde:\n{respuesta}\n")
                
                print("="*80)
                print("✅ Consulta completada exitosamente")
                print("="*80)
                
    except Exception as e:
        print(f"\n❌ Error al conectar con servidor MCP: {e}")
        print("\n💡 Asegúrate de que el servidor esté corriendo:")
        print("   python jefe_seguridad_server.py")
        raise

if __name__ == "__main__":
    print("\n🚀 Iniciando cliente MCP del Oficial de Operaciones...\n")
    asyncio.run(consultar_jefe_seguridad())
