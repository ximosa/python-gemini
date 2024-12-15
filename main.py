import streamlit as st
import google.generativeai as genai
import os
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')
code_model = genai.GenerativeModel('code-bison')

# --- Inicialización del historial del chat ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

# --- Función para generar código con contexto ---
def generate_response(prompt, chat_history):
    """Genera texto o código con el modelo Gemini, incluyendo el contexto de la conversación."""
    try:
        full_prompt = ""
        for speaker, message in chat_history:
            full_prompt += f"{speaker}: {message}\n"
        full_prompt += f"Usuario: {prompt}\n"
        print("Prompt generado:", full_prompt)
        if "genera" in prompt.lower() or "codigo" in prompt.lower() or "code" in prompt.lower():
            response = code_model.generate_content(full_prompt)
        else:
            response = model.generate_content(full_prompt)
        print("Respuesta API recibida:", response)
        if response.text:
            return response.text
        else:
            return "No se pudo generar respuesta."
    except Exception as e:
        print("Error en generate_response:", e)
        return f"Ocurrió un error al interactuar con la API: {e}"

def format_code(text):
   try:
        lexer = guess_lexer(text)
        formatter = HtmlFormatter()
        return highlight(text, lexer, formatter)
   except:
      return None

def is_code(text):
   try:
       guess_lexer(text)
       return True
   except:
      return False

# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")

# Visualizar el historial del chat
for speaker, message in st.session_state['chat_history']:
  with st.chat_message(speaker.lower()):
    if is_code(message):
        formatted_code = format_code(message)
        if formatted_code:
          st.markdown(formatted_code, unsafe_allow_html=True)
        else:
           st.write(message)
    else:
      st.write(message)

# Área de entrada de texto
user_input = st.chat_input("Escribe tu mensaje aquí:")

# --- Lógica del chat ---
if user_input:
  st.session_state['chat_history'].append(("Usuario", user_input))
  print("Historial del chat actualizado:", st.session_state['chat_history'])
    # Generar respuesta con contexto
  generated_text = generate_response(user_input, st.session_state['chat_history'])
  print("Texto generado:", generated_text)
  st.session_state['chat_history'].append(("Assistant", generated_text))
  print("Historial del chat actualizado:", st.session_state['chat_history'])
