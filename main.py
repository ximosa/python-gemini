import streamlit as st
import google.generativeai as genai
import os

# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')
available_models = genai.list_models()

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

# --- Función para generar respuesta ---
def generate_response(prompt, chat_history):
  """Genera texto con el modelo Gemini, incluyendo el contexto de la conversación."""
  try:
    full_prompt = ""
    for speaker, message in chat_history:
        full_prompt += f"{speaker}: {message}\n"
    full_prompt += f"Usuario: {prompt}\n"
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

# Visualizar el historial del chat
for speaker, message in st.session_state['chat_history']:
    with st.chat_message(speaker.lower()):
        st.write(message)

    # Generar respuesta con contexto
    generated_text = gemini_api.generate_response(user_input, chat.get_history())
    print("Texto generado:", generated_text)
    chat.add_message("Assistant", generated_text)
    # Mostrar la respuesta
    with st.chat_message("assistant"):
        if user_input.lower().startswith("genera código") or user_input.lower().startswith("code") or is_code(generated_text):
             st.code(generated_text, language="python")
        else:
            st.write(generated_text)

# Visualizar el historial del chat
for speaker, message in chat.get_history():
   with st.chat_message(speaker.lower()):
      if is_code(message):
         st.code(message, language="python")
      else:
        st.write(message)
