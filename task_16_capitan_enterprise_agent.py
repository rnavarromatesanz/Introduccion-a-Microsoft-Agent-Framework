import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _quitar_acentos_simple(s: str) -> str:
    tabla = str.maketrans(
        {
            "Á": "A",
            "É": "E",
            "Í": "I",
            "Ó": "O",
            "Ú": "U",
            "Ä": "A",
            "Ë": "E",
            "Ï": "I",
            "Ö": "O",
            "Ü": "U",
            "À": "A",
            "È": "E",
            "Ì": "I",
            "Ò": "O",
            "Ù": "U",
            "Ñ": "N",
        }
    )
    return s.translate(tabla)


def _normalizar(texto: str) -> str:
    return _quitar_acentos_simple(texto.upper())


def _nivel_riesgo(texto: str) -> str:
    t = _normalizar(texto)
    if "CRITICO" in t or "CRITICA" in t:
        return "CRÍTICO"
    if "ALTO" in t:
        return "ALTO"
    if "MEDIO" in t:
        return "MEDIO"
    if "BAJO" in t:
        return "BAJO"
    return "NO ESPECIFICADO"


def _extraer_claves(texto: str, max_lineas: int = 4) -> list[str]:
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    if not lineas:
        return []

    claves = [
        l
        for l in lineas
        if _normalizar(l).startswith(
            (
                "RIESGO:",
                "RECOMENDACION:",
                "JUSTIFICACION:",
                "CONCLUSION:",
                "ACCION:",
                "ACCION ",
            )
        )
    ]
    return (claves[:max_lineas] if claves else lineas[:max_lineas])


async def consultar_puente_enterprise_mcp(task: str, especialistas: list[str] | None = None) -> str:
    """Consulta a especialistas (agentes) del Puente del Enterprise vía MCP.

    Devuelve un JSON (string) con:
    - herramientas_disponibles
    - respuestas: [{especialista, riesgo_detectado, claves, respuesta}]
    - errores: [{especialista, error}]

    Nota: esta herramienta *inicia* el servidor MCP mediante stdio (subproceso) y lo consulta.
    """

    script_dir = Path(__file__).resolve().parent
    venv_python = script_dir / ".MAFvenv" / "Scripts" / "python.exe"
    server_python = str(venv_python) if venv_python.exists() else sys.executable

    server_params = StdioServerParameters(
        command=server_python,
        args=["task_16_puente_enterprise_server.py"],
        env=None,
    )

    respuestas: list[dict[str, Any]] = []
    errores: list[dict[str, str]] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            herramientas_disponibles = [t.name for t in tools.tools]

            if especialistas:
                # Filtrar a las solicitadas (sin fallar si hay alguna que no exista)
                solicitadas = [e for e in especialistas if e in herramientas_disponibles]
                a_consultar = solicitadas if solicitadas else herramientas_disponibles
            else:
                a_consultar = herramientas_disponibles

            for tool_name in a_consultar:
                try:
                    resultado = await session.call_tool(
                        name=tool_name,
                        arguments={"task": task},
                    )

                    if hasattr(resultado, "content") and resultado.content:
                        content_items = (
                            resultado.content if isinstance(resultado.content, list) else [resultado.content]
                        )
                        partes: list[str] = []
                        for item in content_items:
                            partes.append(str(getattr(item, "text", item)))
                        texto = "\n".join([p for p in partes if p]).strip()
                    else:
                        texto = str(resultado)

                    respuestas.append(
                        {
                            "especialista": tool_name,
                            "riesgo_detectado": _nivel_riesgo(texto),
                            "claves": _extraer_claves(texto, max_lineas=4),
                            "respuesta": texto,
                        }
                    )
                except Exception as e:  # noqa: BLE001 (workshop)
                    errores.append({"especialista": tool_name, "error": str(e)})

    payload = {
        "herramientas_disponibles": herramientas_disponibles,
        "respuestas": respuestas,
        "errores": errores,
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _cargar_env() -> None:
    """Carga variables desde .env (sin depender de python-dotenv).

    - No sobreescribe variables ya definidas en el entorno.
    - Soporta valores entre comillas simples o dobles.
    """

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\ufeff")

        if not key or key in os.environ:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ[key] = value


def _azure_openai_url(base_url: str, deployment: str, api_version: str) -> tuple[str, bool]:
        """Devuelve (url, is_openai_v1).

        - Si el endpoint es OpenAI-compatible (termina en /openai/v1 o /openai/v1/):
            - URL: <base>/chat/completions
            - Se debe enviar el campo 'model' en el payload.

        - Si es Azure "deployments":
            - URL: <base>/openai/deployments/<deployment>/chat/completions?api-version=...
            - No es necesario enviar 'model'.
        """

        base = base_url.rstrip("/")
        if base.endswith("/openai/v1"):
                return f"{base}/chat/completions", True
        return f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}", False


def _azure_chat_completions(
    *,
    base_url: str,
    api_key: str,
    deployment: str,
    api_version: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | str | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    url, is_openai_v1 = _azure_openai_url(base_url, deployment, api_version)

    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
    }

    if is_openai_v1:
        payload["model"] = deployment

    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def _tool_schema_consultar_puente() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "consultar_puente_enterprise_mcp",
            "description": "Consulta a especialistas del Puente del Enterprise vía MCP y devuelve un JSON con sus respuestas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Escenario o pregunta para los especialistas"},
                    "especialistas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista opcional de especialistas a consultar; si se omite se consultan todos",
                    },
                },
                "required": ["task"],
            },
        },
    }


async def _run_capitan(escenario: str) -> str:
    _cargar_env()

    base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-02-15-preview"

    if not base_url or not api_key or not deployment:
        raise RuntimeError(
            "Faltan variables de entorno. Configura AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY y AZURE_OPENAI_DEPLOYMENT. "
            "Opcional: AZURE_OPENAI_API_VERSION."
        )

    system_prompt = """Eres el Capitán del Enterprise-D.
Tu misión es tomar una decisión final tras consultar a especialistas (agentes) vía MCP.

REGLAS OBLIGATORIAS:
1) Antes de decidir, SIEMPRE llama a la herramienta consultar_puente_enterprise_mcp.
2) Política de decisión (heurística estable para el workshop):
   - Si algún especialista reporta riesgo CRÍTICO o ALTO → DECISIÓN = NO AUTORIZAR
   - Si no hay ALTO/CRÍTICO pero hay MEDIO → DECISIÓN = AUTORIZAR CON MITIGACIONES
   - Si no hay ALTO/CRÍTICO/MEDIO → DECISIÓN = AUTORIZAR
3) Cita evidencias concretas devueltas por los especialistas.
4) No ejecutes acciones: solo recomendación/decisión y siguientes pasos.

FORMATO DE SALIDA (exacto):
DECISIÓN: <NO AUTORIZAR|AUTORIZAR CON MITIGACIONES|AUTORIZAR>
MOTIVO: <explicación de 3-6 líneas>
EVIDENCIAS:
- <especialista>: <1-2 bullets cortos con evidencias>
MITIGACIONES / SIGUIENTES PASOS:
- <lista de 3-6 acciones>
"""

    tools = [_tool_schema_consultar_puente()]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Escenario del Capitán:\n" + escenario + "\n\n" + "Consulta a los especialistas vía MCP y emite la decisión final."
            ),
        },
    ]

    # 1) Primer turno: el modelo debería pedir la herramienta
    resp1 = _azure_chat_completions(
        base_url=base_url,
        api_key=api_key,
        deployment=deployment,
        api_version=api_version,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )

    msg1 = (resp1.get("choices") or [{}])[0].get("message") or {}
    tool_calls = msg1.get("tool_calls") or []

    if not tool_calls:
        # Fallback: si el modelo no llama herramienta, forzamos una llamada y pedimos síntesis.
        tool_result = await consultar_puente_enterprise_mcp(task=escenario)
        messages.append({"role": "assistant", "content": msg1.get("content") or ""})
        messages.append({"role": "tool", "tool_call_id": "forced", "content": tool_result})
    else:
        # Guardamos el mensaje del asistente con tool_calls
        messages.append(
            {
                "role": "assistant",
                "content": msg1.get("content"),
                "tool_calls": tool_calls,
            }
        )

        for call in tool_calls:
            fn = (call.get("function") or {})
            name = fn.get("name")
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw)
            except Exception:  # noqa: BLE001 (workshop)
                args = {"task": escenario}

            if name != "consultar_puente_enterprise_mcp":
                result = json.dumps({"error": f"Tool no soportada: {name}"}, ensure_ascii=False)
            else:
                especialistas_arg = args.get("especialistas")
                especialistas_list: list[str] | None
                if especialistas_arg is None:
                    especialistas_list = None
                elif isinstance(especialistas_arg, list):
                    especialistas_list = [str(x) for x in especialistas_arg]
                else:
                    especialistas_list = [str(especialistas_arg)]

                result = await consultar_puente_enterprise_mcp(
                    task=str(args.get("task") or escenario),
                    especialistas=especialistas_list,
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or "unknown",
                    "content": result,
                }
            )

    # 2) Segundo turno: respuesta final
    resp2 = _azure_chat_completions(
        base_url=base_url,
        api_key=api_key,
        deployment=deployment,
        api_version=api_version,
        messages=messages,
        tools=tools,
        temperature=0.2,
    )

    msg2 = (resp2.get("choices") or [{}])[0].get("message") or {}
    return str(msg2.get("content") or "")


async def main() -> None:
    print("=" * 80)
    print("🧠 AGENTE ORQUESTADOR MCP: Capitán del Enterprise")
    print("=" * 80)

    #una anomalía espacial tipo Tiburón Nebular. Parece estar acercándose a la nave con velocidad warp 5.
    #un sistema con un planeta de la federación con muchas playas y lugares de esparcimiento, sería una buena parada para la tripulación
    escenario = """Estamos pasando por una anomalía espacial tipo Tiburón Nebular. Parece estar acercándose a la nave con velocidad warp 5.
Necesito evaluación inmediata de:
1. ¿Qué es este fenómeno científicamente?
2. ¿Puede el Enterprise escapar?
3. ¿Cuál es el riesgo para la tripulación?
4. ¿Hay impacto médico potencial?"""
    print(escenario)
    texto = await _run_capitan(escenario)

    print("\n" + "=" * 80)
    print("✅ DECISIÓN FINAL (AGENTE CAPITÁN)")
    print("=" * 80)
    print(texto)


if __name__ == "__main__":
    asyncio.run(main())
