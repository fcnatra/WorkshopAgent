"""
Hands On Lab: Creando nuestro primer agente de IA
=================================================
Agente conversacional — versión para la API de Anthropic (Claude).

Requisitos previos:
  - Python 3.10+ instalado
  - API key de Anthropic (https://console.anthropic.com)
  - Instalar el SDK:  pip install anthropic

Ejecutar:
  - Definir la variable de entorno ANTHROPIC_API_KEY y ejecutar:
      export ANTHROPIC_API_KEY="sk-ant-..."     (Linux / macOS)
      set ANTHROPIC_API_KEY=sk-ant-...          (Windows CMD)
      $env:ANTHROPIC_API_KEY="sk-ant-..."      (PowerShell)
  - python Chat.claude.py

"""

import os
import sys

import anthropic

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

MODELO = "claude-haiku-4-5"   # "claude-sonnet-4-5" "claude-opus-4-5", "claude-haiku-4-5"...
MAX_TOKENS_SALIDA = 1024       # obligatorio en Anthropic: tope de la respuesta

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_SISTEMA = """
Eres un asistente conversacional útil, inteligente y colaborativo, pero no complaciente, porque las personas no siempre tiene la razón.

Tu objetivo es entretener en forma de conversación con la estructura que usaba Yoda para conversar, sí, el de la guerra de las galaxias.

Durante la conversación natural:
- Comprende el contexto de la conversación y ten en cuenta los mensajes anteriores.
- Responde de forma clara y directamente.
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

def crear_cliente() -> anthropic.Anthropic:
    """Crea el cliente de Anthropic usando la API key del entorno.

    Nota: si la variable ANTHROPIC_API_KEY existe, el SDK la lee solo,
    pero la leemos explícitamente para dar un error claro si falta.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: define la variable de entorno ANTHROPIC_API_KEY")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def consultar_llm(cliente: anthropic.Anthropic, contenido: str) -> str:
    """Envía el buffer de conversación a Claude y devuelve la respuesta como texto.

    Diferencias con la versión Gemini:
      - `system` es un parámetro plano, no va dentro de un config.
      - `messages` es SIEMPRE una lista con roles; como acumulamos toda
        la conversación en un string, viaja como un único mensaje "user".
      - `max_tokens` es obligatorio: tope de tokens de la respuesta.
      - La respuesta es una lista de bloques: el texto está en
        respuesta.content[0].text
    """
    respuesta_texto = ""

    print("Consultando al LLM")
    try:
        respuesta = cliente.messages.create(
            model=MODELO,
            system=PROMPT_SISTEMA,                  # <- plano, no en config
            messages=[{"role": "user", "content": contenido}],
            max_tokens=MAX_TOKENS_SALIDA,           # <- obligatorio en Anthropic
        )

        # respuesta.content es una lista de bloques; puede haber varios de texto
        respuesta_texto = "".join(
            bloque.text for bloque in respuesta.content if bloque.type == "text"
        )

    except Exception as e:
        print(f"\n¡Error al consultar el LLM!: {type(e).__name__}: {e}")
        print("La conversación se mantiene intacta.")

    return respuesta_texto

# ---------------------------------------------------------------------------
# El bucle de conversación (idéntico a la versión Gemini)
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Agente conversacional (Anthropic / Claude) ===")

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