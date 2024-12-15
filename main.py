import streamlit as st
import google.generativeai as genai
import os
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

# --- Clases y Funciones ---

class GeminiAPI:
    def __init__(self, api_key):
      genai.configure(api_key=api_key)
      self.model = genai.GenerativeModel('gemini-pro')
      available_models = genai.list_models()

      code_model_name = None
      for m in available_models:
          if 'code' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
              code_model_name = m.name
              break
      if code_model_name:
          self.code_model = genai.GenerativeModel(code_model_name)
          print(f"Usando modelo para código: {code_model_name}")
      else:
          self.code_model = self.model
          print("No se encontró un modelo específico para código, usando gemini-pro")

    def generate_response(self, prompt, chat_history):
        """Genera texto o código con el modelo Gemini, incluyendo el contexto de la conversación."""
        try:
          full_prompt = ""
          for speaker, message in chat_history:
              full_prompt += f"{speaker}: {message}\n"
          full_prompt += f"Usuario: {prompt}\n"
          print("Prompt generado:", full_prompt)
          if prompt.lower().startswith("genera código") or prompt.lower().startswith("code"):
             response = self.code_model.generate_content(full_prompt)
          else:
             response = self.model.generate_content(full_prompt)
          print("Respuesta API recibida:", response)
          if response.text:
              return response.text
          else:
              return "No se pudo generar respuesta."
        except Exception as e:
            print("Error en generate_response:", e)
            return f"Ocurrió un error al interactuar con la API: {e}"


class Chat:
  def __init__(self):
    if 'chat_history' not in st.session_state:
      st.session_state['chat_history'] = []
    self.history = st.session_state['chat_history']

  def add_message(self, speaker, message):
    self.history.append((speaker, message))
    print("Historial del chat actualizado:", self.history)

  def get_history(self):
      return self.history

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


# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()

gemini_api = GeminiAPI(API_KEY)
chat = Chat()
# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")

# Área de entrada de texto
user_input = st.chat_input("Escribe tu mensaje aquí:")

# --- Lógica del chat ---
if user_input:
    chat.add_message("Usuario", user_input)

    # Generar respuesta con contexto
    generated_text = gemini_api.generate_response(user_input, chat.get_history())
    print("Texto generado:", generated_text)
    chat.add_message("Assistant", generated_text)
    # Mostrar la respuesta
    with st.chat_message("assistant"):
       if is_code(generated_text):
           formatted_code = format_code(generated_text)
           if formatted_code:
               st.markdown(formatted_code, unsafe_allow_html=True)
           else:
               st.write(generated_text)
       else:
            st.write(generated_text)

# Visualizar el historial del chat
for speaker, message in chat.get_history():
   with st.chat_message(speaker.lower()):
      if is_code(message):
        formatted_code = format_code(message)
        if formatted_code:
          st.markdown(formatted_code, unsafe_allow_html=True)
        else:
          st.write(message)
      else:
           st.write(message)
