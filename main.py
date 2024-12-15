import streamlit as st
import google.generativeai as genai
import os

# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)

available_models = genai.list_models()
model_options = [m.name for m in available_models if 'generateContent' in m.supported_generation_methods]

if not model_options:
   st.error("No se encontró ningún modelo válido para la API")
   st.stop()
else:
   print(f"Lista de modelos disponibles: {model_options}")

if 'selected_model' not in st.session_state:
    if 'gemini-pro' in model_options:
      st.session_state['selected_model'] = 'gemini-pro'
    else:
        st.session_state['selected_model'] = model_options[0]


try:
    selected_model_name = st.selectbox("Selecciona un modelo:", model_options, index = model_options.index(st.session_state['selected_model']))
    st.session_state['selected_model'] = selected_model_name
except Exception as e:
    st.error(f"Error al seleccionar el modelo: {e}. Seleccionando modelo por defecto: {model_options[0]}")
    selected_model_name = model_options[0]
    st.session_state['selected_model'] = selected_model_name


model = genai.GenerativeModel(selected_model_name)

code_model_name = None
for m in available_models:
    if 'code' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
        code_model_name = m.name
        break

if code_model_name:
    code_model = genai.GenerativeModel(code_model_name)
    print(f"Usando modelo para código: {code_model_name}")
else:
    code_model = model
    print("No se encontró un modelo específico para código, usando gemini-pro")

# --- Inicialización del historial del chat ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []


if 'custom_prompt' not in st.session_state:
    st.session_state['custom_prompt'] = ""

# --- Clase Chat  ---
class Chat:
    def __init__(self):
       self.history = st.session_state['chat_history']
    def add_message(self, speaker, message):
        self.history.append((speaker, message))
        print("Historial del chat actualizado:", self.history)
    def get_history(self):
      return self.history

# --- Función para generar respuesta ---
def generate_response(prompt, chat_history, custom_prompt):
  """Genera texto con el modelo Gemini, incluyendo el contexto de la conversación."""
  try:
    full_prompt = ""
    for speaker, message in chat_history:
        full_prompt += f"{speaker}: {message}\n"
    full_prompt += f"Usuario: {prompt}\n"
    full_prompt += f"{custom_prompt}\n"
    print("Prompt generado:", full_prompt)
    if prompt.lower().startswith("genera código") or prompt.lower().startswith("code"):
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

# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")
# Inicializamos el chat como un objeto
chat = Chat()

custom_prompt = st.text_area("Instrucciones adicionales para la IA (opcional):", value = st.session_state['custom_prompt'])
st.session_state['custom_prompt'] = custom_prompt
# Área de entrada de texto
user_input = st.chat_input("Escribe tu mensaje aquí:")

# --- Lógica del chat ---
if user_input:
    chat.add_message("Usuario", user_input)
    # Generar respuesta con contexto
    generated_text = generate_response(user_input, chat.get_history(), custom_prompt)
    print("Texto generado:", generated_text)
    chat.add_message("Assistant", generated_text)

# Visualizar el historial del chat
for speaker, message in chat.get_history():
    with st.chat_message(speaker.lower()):
        st.write(message)
