"""
Hands On Lab: Creando nuestro primer agente de IA
=================================================
Agente refinador de requisitos — el primer agente de la "factoría".

Qué hace:
  1. Vigila una carpeta local buscando archivos de requisitos (R-*.txt)
  2. Envía su contenido a Gemini (LLM) con instrucciones de análisis
  3. Si los requisitos son ambiguos -> añade preguntas al final del propio R-*.txt
  4. Si están claros -> genera historias de usuario y las guarda como US-XXX.txt

Requisitos previos:
  - Python 3.10+ instalado
  - API key de Google AI Studio (https://aistudio.google.com)
  - Instalar el SDK:  pip install google-genai

Ejecutar:
  - Definir la variable de entorno GEMINI_API_KEY y ejecutar:
      export GEMINI_API_KEY="AIza..."        (Linux / macOS)
      set GEMINI_API_KEY=AIza...             (Windows CMD)
      $env:GEMINI_API_KEY="AIza..."         (PowerShell)
  - python agente_requisitos.py

Convención de archivos en la carpeta vigilada:
  R-*.txt  -> archivo de requisitos (entrada del agente)
  US-*.txt -> historias de usuario (salida del agente)
"""

import glob
import json
import os
import re
import sys

from google import genai

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CARPETA_VIGILADA = "especificaciones"   # carpeta con los R-*.txt
MODELO = "gemini-3.8-flash"             # modelo gratuito de la API de Gemini

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
# Nivel 3 (stretch): herramienta que el LLM puede invocar si quiere
# ---------------------------------------------------------------------------

GUIA_HISTORIAS = """Guía de buenas historias de usuario:
- Independientes, negociables, valiosas para el usuario.
- Estimables y pequeñas (caben en un sprint).
- Testables: cada historia tiene criterios de aceptación verificables.
- Escritas en lenguaje de negocio, no técnico.
- Formato: Como <rol>, quiero <objetivo>, para <beneficio>.
"""


# La "tool" es simplemente una función Python con un docstring claro:
# el LLM lee el nombre, la descripción y decide si invocarla.

def obtener_guia_historias() -> str:
    """Devuelve la guía de cómo escribir buenas historias de usuario.

    Úsala cuando vayas a redactar historias de usuario y quieras
    comprobar las reglas de calidad (formato, criterios, tamaño).
    """
    print(f"El LLM ha pedido la guía de historias de usuario")
    return GUIA_HISTORIAS

# ---------------------------------------------------------------------------
# Conexión con el LLM
# ---------------------------------------------------------------------------

def crear_cliente() -> genai.Client:
    """Crea el cliente de Gemini usando la API key del entorno."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: define la variable de entorno GEMINI_API_KEY")
        print("  export GEMINI_API_KEY='AIza...'")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def consultar_llm(cliente: genai.Client, archivo: str, contenido: str) -> dict:
    """Envía los requisitos a Gemini y devuelve la respuesta como dict.

    Usamos "JSON mode" (response_mime_type) para que el LLM responda
    SIEMPRE en JSON: así el parsing es fiable.
    """
    print(f"Consultado el LLM")
    respuesta = cliente.models.generate_content(
        model=MODELO,
        contents=PROMPT_USUARIO.format(archivo=archivo, contenido=contenido),
        config=genai.types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA,
            response_mime_type="application/json",  # <- JSON mode
        ),
    )
    return json.loads(respuesta.text)


def consultar_llm_con_tool(cliente: genai.Client, archivo: str, contenido: str) -> dict:
    """NIVEL 3 (avanzado): igual que consultar_llm, pero le damos al LLM
    una herramienta (obtener_guia_historias) que puede decidir usar.

    El SDK ejecuta la función Python automáticamente cuando el LLM la
    pide ("automatic function calling") y le envía el resultado para que
    continúe. Nosotros solo recibimos la respuesta final en JSON.
    """
    print(f"Consultado el LLM")
    chat = cliente.chats.create(
        model=MODELO,
        config=genai.types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA,
            response_mime_type="application/json",  # <- JSON mode
            tools=[obtener_guia_historias],         # <- la tool disponible
        ),
    )
    respuesta = chat.send_message(
        PROMPT_USUARIO.format(archivo=archivo, contenido=contenido)
    )
    return json.loads(respuesta.text)

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
# El bucle del agente
# ---------------------------------------------------------------------------

def procesar_archivo(cliente: genai.Client, carpeta: str, archivo: str, contenido: str) -> None:
    """Ciclo completo para un archivo de requisitos."""
    print(f"\nProcesando {archivo}...")

    # 1. Consultar al LLM
    #    - Nivel 1-2: consultar_llm(...)          (sin herramienta)
    #    - Nivel 3:   consultar_llm_con_tool(...) (el LLM decide si usar la tool)
    resultado = consultar_llm_con_tool(cliente, archivo, contenido)

    # 2. Actuar según la decisión del LLM
    if resultado.get("decision") == "refinar":
        escribir_preguntas(carpeta, archivo, resultado.get("preguntas", []))
    else:
        escribir_historias(carpeta, resultado.get("historias", []))


def main() -> None:
    print("=== Agente refinador de requisitos ===")
    print(f"Carpeta vigilada: {CARPETA_VIGILADA}/")

    # 1. Leer los requisitos del disco
    requisitos = leer_requisitos(CARPETA_VIGILADA)
    if not requisitos:
        print(f"No se encontraron archivos R-*.txt en {CARPETA_VIGILADA}/")
        print("Crea uno de ejemplo, p. ej. R-001.txt con 3-4 frases.")
        return

    # 2. Conectar con el LLM
    cliente = crear_cliente()

    # 3. Procesar cada archivo
    for archivo, contenido in requisitos.items():
        procesar_archivo(cliente, CARPETA_VIGILADA, archivo, contenido)

    print("\nFin. Revisa la carpeta para ver el resultado.")


if __name__ == "__main__":
    main()