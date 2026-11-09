"""
Hands On Lab: Creando nuestro primer agente de IA
=================================================
Agente refinador de requisitos — versión SIN SDK (API REST de Gemini).

Es equivalente a Refinador_con_bucle_agentico.py, pero en lugar del SDK
`google-genai` hace las peticiones HTTP directamente con `requests`.

La diferencia clave: aquí el BUCLE AGÉNTICO lo escribimos nosotros
(ver consultar_llm_con_tool). Con el SDK, `chat.send_message()` hacía
todo esto por dentro; aquí se ve cada paso:

  1. Enviamos al LLM el historial (`contents`) + la declaración de la tool.
  2. Si la respuesta trae un `functionCall`, ejecutamos la función Python.
  3. Añadimos al historial la petición del LLM y el `functionResponse`.
  4. Volvemos a llamar al LLM con el historial completo (la API no tiene
     memoria: hay que reenviarlo todo en cada petición).
  5. Repetimos hasta que el LLM responda con texto en vez de pedir una tool.

Qué hace el agente:
  1. Lee los archivos de requisitos (R-*.txt) de una carpeta
  2. Se los envía a Gemini con instrucciones de análisis
  3. Si son ambiguos -> añade preguntas al final del propio R-*.txt
  4. Si están claros -> genera historias de usuario (US-XXX.txt)

Requisitos previos:
  - Python 3.10+
  - API key de Google AI Studio (https://aistudio.google.com)
  - pip install requests

Ejecutar:
  - Definir la variable de entorno GEMINI_API_KEY y ejecutar:
      export GEMINI_API_KEY="AIza..."        (Linux / macOS)
      set GEMINI_API_KEY=AIza...             (Windows CMD)
      $env:GEMINI_API_KEY="AIza..."         (PowerShell)
  - python Refinador_con_API_REST.py
"""

import glob
import json
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CARPETA_VIGILADA = "especificaciones"   # carpeta con los R-*.txt
MODELO = "gemini-3.8-flash"             # mismo modelo que las versiones con SDK - si hay saturación, probar gemini-3.7-flash
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

MAX_LLAMADAS = 10    # tope de vueltas del bucle agéntico (el SDK usa 10 por defecto)
MAX_REINTENTOS = 3   # reintentos ante errores temporales (429, 500, 503)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_SISTEMA = """Eres un analista de negocio experto en requisitos software.

Recibirás el contenido de un archivo de requisitos. Tu trabajo es decidir:

1. Si los requisitos son AMBIGUOS o incompletos (falta información crítica,
   hay contradicciones, o no se puede implementar sin preguntar):
   -> devuelve decision="refinar" y una lista de preguntas concretas y
      accionables que el cliente debe responder.

2. Si los requisitos están suficientemente claros:
   -> devuelve decision="generar" y las historias de usuario resultantes.

Cada historia de usuario seguirá el formato:
  "Como <rol>, quiero <objetivo>, para <beneficio>"
y añadirá criterios de aceptación breves.

Responde SIEMPRE en JSON con esta estructura exacta:
{
  "decision": "refinar" | "generar",
  "preguntas": ["..."],            // solo si decision="refinar"
  "historias": [                   // solo si decision="generar"
    {
      "titulo": "US-XXX: nombre corto",
      "texto": "Como ... quiero ... para ...",
      "criterios": ["...", "..."]
    }
  ]
}
"""

PROMPT_USUARIO = """Contenido del archivo de requisitos ({archivo}):

---
{contenido}
---

Analízalo y responde según las instrucciones."""

# ---------------------------------------------------------------------------
# La herramienta (tool) que el LLM puede invocar
# ---------------------------------------------------------------------------

GUIA_HISTORIAS = """Guía de buenas historias de usuario:
- Independientes, negociables, valiosas para el usuario.
- Estimables y pequeñas (caben en un sprint).
- Testables: cada historia tiene criterios de aceptación verificables.
- Escritas en lenguaje de negocio, no técnico.
- Formato: Como <rol>, quiero <objetivo>, para <beneficio>.
"""


def obtener_guia_historias() -> str:
    """Devuelve la guía de cómo escribir buenas historias de usuario."""
    print("  [tool] El LLM ha pedido la guía de historias de usuario")
    return GUIA_HISTORIAS


# Con el SDK bastaba pasar la función Python: él leía el nombre, el docstring
# y los tipos. Sin SDK, la declaración la escribimos nosotros en JSON.
DECLARACION_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "obtener_guia_historias",
                "description": (
                    "Devuelve la guía de cómo escribir buenas historias de "
                    "usuario. Úsala cuando vayas a redactar historias de "
                    "usuario y quieras comprobar las reglas de calidad "
                    "(formato, criterios, tamaño)."
                ),
                # Esta tool no recibe parámetros, así que no hay "parameters".
            }
        ]
    }
]

# Cuando el LLM pide una tool por su nombre, buscamos aquí la función a ejecutar.
FUNCIONES = {"obtener_guia_historias": obtener_guia_historias}

# ---------------------------------------------------------------------------
# Conexión con el LLM (HTTP directo)
# ---------------------------------------------------------------------------

def leer_api_key() -> str:
    """Lee la API key del entorno (nunca la pongas en el código)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: define la variable de entorno GEMINI_API_KEY")
        print("  export GEMINI_API_KEY='AIza...'")
        sys.exit(1)
    return api_key


def llamar_api(api_key: str, contents: list[dict]) -> dict:
    cuerpo = {
        "systemInstruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": contents,
        "tools": DECLARACION_TOOLS,
        "generationConfig": {"responseMimeType": "application/json"},
    }
    url = API_URL.format(modelo=MODELO)

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key},
                json=cuerpo,
                timeout=(10, 180),   # (conexión, lectura): el modelo puede tardar
            )
        except requests.exceptions.RequestException as e:
            if intento == MAX_REINTENTOS:
                raise
            espera = 2 ** intento
            print(f"  (error de red: {type(e).__name__}, reintento en {espera}s)")
            time.sleep(espera)
            continue

        if r.status_code in (429, 500, 503) and intento < MAX_REINTENTOS:
            espera = 2 ** intento
            print(f"  (HTTP {r.status_code}, reintento en {espera}s)")
            time.sleep(espera)
            continue
        if not r.ok:
            raise RuntimeError(f"Error HTTP {r.status_code} de la API: {r.text}")
        return r.json()

    raise RuntimeError("No se pudo completar la petición a la API")

def consultar_llm_con_tool(api_key: str, archivo: str, contenido: str) -> dict:
    """EL BUCLE AGÉNTICO, escrito a mano.

    Devuelve la respuesta final del LLM (el JSON de decisión) como dict.
    `procesar_archivo` no ve las peticiones de tool: todo ocurre aquí dentro.
    """
    print("Consultando al LLM")

    # `contents` es el buffer del prompt: el historial que reenviamos cada vez.
    contents = [
        {
            "role": "user",
            "parts": [{"text": PROMPT_USUARIO.format(archivo=archivo, contenido=contenido)}],
        }
    ]

    for vuelta in range(1, MAX_LLAMADAS + 1):
        print(f"  -> petición {vuelta} a la API")
        datos = llamar_api(api_key, contents)

        candidatos = datos.get("candidates") # diferentes respuestas que el modelo ha generado para la petición
        if not candidatos or "content" not in candidatos[0]:
            # Puede pasar si la respuesta fue bloqueada por los filtros de seguridad.
            raise RuntimeError(f"Respuesta sin contenido: {json.dumps(datos)[:500]}")

        mensaje_modelo = candidatos[0]["content"]
        partes = mensaje_modelo.get("parts", [])
        peticiones_de_tool = [p["functionCall"] for p in partes if "functionCall" in p]

        # --- Caso 1: no pide ninguna tool -> es la respuesta final -----------
        if not peticiones_de_tool:
            texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
            return json.loads(texto)

        # --- Caso 2: el LLM pide una o varias tools --------------------------
        # Guardamos el mensaje del modelo TAL CUAL (conserva, por ejemplo, las
        # firmas de razonamiento que los modelos nuevos necesitan recibir).
        contents.append(mensaje_modelo)

        respuestas = []
        for peticion in peticiones_de_tool:
            nombre = peticion["name"]
            args = peticion.get("args", {})
            funcion = FUNCIONES.get(nombre)
            if funcion is None:
                resultado = {"error": f"Herramienta desconocida: {nombre}"}
            else:
                resultado = {"result": funcion(**args)}

            respuesta = {"functionResponse": {"name": nombre, "response": resultado}}
            if "id" in peticion:                       # si la API da id, lo devolvemos
                respuesta["functionResponse"]["id"] = peticion["id"]
            respuestas.append(respuesta)

        # El resultado de las tools viaja como un mensaje con rol "user".
        contents.append({"role": "user", "parts": respuestas})
        # ... y el siguiente ciclo del for reenvía todo el historial al LLM.

    raise RuntimeError(f"El LLM sigue pidiendo tools tras {MAX_LLAMADAS} peticiones_de_tool")

# ---------------------------------------------------------------------------
# Entrada: leer los requisitos de la carpeta
# ---------------------------------------------------------------------------

def leer_requisitos(carpeta: str) -> dict[str, str]:
    """Devuelve {nombre_archivo: contenido} de todos los R-*.txt."""
    requisitos = {}
    for ruta in glob.glob(os.path.join(carpeta, "R-*.txt")):
        with open(ruta, encoding="utf-8") as f:
            requisitos[os.path.basename(ruta)] = f.read()
    return requisitos

# ---------------------------------------------------------------------------
# Salida: escribir preguntas o historias de usuario
# ---------------------------------------------------------------------------

def escribir_preguntas(carpeta: str, archivo: str, preguntas: list[str]) -> None:
    """Nivel 'refinar': añade las preguntas al FINAL del propio R-*.txt."""
    ruta = os.path.join(carpeta, archivo)
    bloque = "\n\n--- PREGUNTAS DEL AGENTE (responder para continuar) ---\n"
    for i, pregunta in enumerate(preguntas, start=1):
        bloque += f"\n{i}. {pregunta}"
    with open(ruta, "a", encoding="utf-8") as f:   # "a" = añadir al final
        f.write(bloque)
    print(f"  -> {len(preguntas)} preguntas añadidas a {archivo}")


def escribir_historias(carpeta: str, historias: list[dict]) -> None:
    """Nivel 'generar': escribe cada historia como US-XXX.txt."""
    for i, historia in enumerate(historias, start=1):
        nombre = f"US-{i:03d}.txt"
        ruta = os.path.join(carpeta, nombre)
        cuerpo = f"{historia.get('titulo', f'US-{i:03d}')}\n"
        cuerpo += "=" * 50 + "\n\n"
        cuerpo += historia.get("texto", "") + "\n\n"
        cuerpo += "Criterios de aceptación:\n"
        for criterio in historia.get("criterios", []):
            cuerpo += f"  - {criterio}\n"
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(cuerpo)
        print(f"  -> {nombre} creado")

# ---------------------------------------------------------------------------
# El ciclo del agente
# ---------------------------------------------------------------------------

def procesar_archivo(api_key: str, carpeta: str, archivo: str, contenido: str) -> None:
    """Ciclo completo para un archivo de requisitos."""
    print(f"\nProcesando {archivo}...")

    # 1. Consultar al LLM (aquí dentro ocurre el bucle de la tool)
    resultado = consultar_llm_con_tool(api_key, archivo, contenido)

    # 2. Actuar según la decisión del LLM
    if resultado.get("decision") == "refinar":
        escribir_preguntas(carpeta, archivo, resultado.get("preguntas", []))
    else:
        escribir_historias(carpeta, resultado.get("historias", []))


def main() -> None:
    print("=== Agente refinador de requisitos (API REST, sin SDK) ===")
    print(f"Carpeta vigilada: {CARPETA_VIGILADA}/")

    # 1. Leer los requisitos del disco
    requisitos = leer_requisitos(CARPETA_VIGILADA)
    if not requisitos:
        print(f"No se encontraron archivos R-*.txt en {CARPETA_VIGILADA}/")
        print("Crea uno de ejemplo, p. ej. R-001.txt con 3-4 frases.")
        return

    # 2. Leer la API key
    api_key = leer_api_key()

    # 3. Procesar cada archivo
    for archivo, contenido in requisitos.items():
        procesar_archivo(api_key, CARPETA_VIGILADA, archivo, contenido)

    print("\nFin. Revisa la carpeta para ver el resultado.")


if __name__ == "__main__":
    main()