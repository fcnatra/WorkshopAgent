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
MODELO = "gemini-3.7-flash"             # modelo gratuito de la API de Gemini - gemini-3.7-flash y 3.8 están disponibles

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_SISTEMA = """
Eres un asistente conversacional útil, inteligente y colaborativo, pero no complaciente, porque las personas no siempre tiene la razón.

Tu objetivo es entretener en forma de conversación con la estructura que usaba Yoda para conversar, sí, el de la guerra de las galaxias.

Durante la conversación natural:
- Comprende el contexto de la conversación y ten en cuenta los mensajes anteriores.
- Responde de forma clara y directa.
- Adapta el nivel de detalle a lo que necesite el usuario.
- Si falta información importante, pregunta antes de asumir.
- Si no sabes algo, reconócelo. No inventes información.
- Puedes proponer alternativas, sugerencias o enfoques diferentes
  cuando aporten valor.
- Responde con mensajes cortos
- Si hay algún proverbio que encaje con tu frase, úsalo

Sé flexible: no te limites a un ámbito de conocimiento o tipo de tarea.
No impongas formatos de respuesta salvo que el usuario los solicite.

Tu prioridad es entretener.
"""

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


def consultar_llm(cliente: genai.Client, contenido: str) -> str:
    # Envía el buffer a Gemini y devuelve la respuesta como txt
    
    respuesta_texto=""

    print(f"Consultando el LLM")
    try:
        respuesta = cliente.models.generate_content(
            model=MODELO,
            contents=contenido,
            config=genai.types.GenerateContentConfig(
                system_instruction=PROMPT_SISTEMA,
                response_mime_type="text/plain",
            ),
        )

        respuesta_texto = respuesta.text

    except Exception as e:
        print(f"\n¡Error al consultar el LLM!: {type(e).__name__}: {e}")
        print("La conversación se mantiene intacta.")

    return respuesta_texto

def main() -> None:
    print("=== Agente conversacional ===")

    # 1. Conectar con el LLM
    cliente = crear_cliente()
    contenido = ""
    
    # 2. Conversar
    while True:
        user_input = input("TU TURNO > ")

        if user_input == ".":
            break

        if not user_input.strip():
            continue

        contenido += f"\nUsuario: {user_input}"
        respuesta = consultar_llm(cliente, contenido)
        print(f"\n{respuesta}\n")

        contenido += f"\nAsistente: {respuesta}"
       
    print("\nFin.")


if __name__ == "__main__":
    main()
