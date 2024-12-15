import streamlit as st
import google.generativeai as genai
import os

# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
print("Clave API cargada") # Añadido
genai.configure(api_key=API_KEY)
print("Configuración de la API completada") # Añadido
model = genai.GenerativeModel('gemini-pro')
print("Modelo cargado") # Añadido


# --- Inicialización del historial del chat ---
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'code_history' not in st.session_state:
    st.session_state['code_history'] = []

# --- Función para generar código con contexto ---
def generate_code_with_context(prompt, chat_history, code_history):
    """Genera código con el modelo Gemini, incluyendo el contexto de la conversación."""
    print("Entrando en generate_code_with_context") # Añadido
    try:
        full_prompt = ""
        for message, code in zip(chat_history, code_history):
            full_prompt += f"Usuario: {message}\n Código generado previamente:\n ```{code}```\n"
        full_prompt += f"Usuario: {prompt}\n"
        print("Prompt generado:", full_prompt) # Añadido
        response = model.generate_content(full_prompt)
        print("Respuesta API recibida:", response) # Añadido
        if response.text:
           return response.text
        else:
            return "No se pudo generar código."
    except Exception as e:
        print("Error en generate_code_with_context:", e) # Añadido
        return f"Ocurrió un error al interactuar con la API: {e}"

# --- Interfaz de Streamlit ---
st.title("Chat de Código con Gemini")

# Visualizar el historial del chat
for message, code in zip(st.session_state['chat_history'], st.session_state['code_history']):
    with st.chat_message("user"):
        st.write(message)
    if code:
        with st.chat_message("assistant"):
            st.code(code, language="python")

# Área de entrada de texto
user_input = st.chat_input("Escribe tu solicitud de código aquí:")
print("Texto ingresado por el usuario:", user_input) # Añadido

# --- Lógica del chat ---
if user_input:
    print("Entrando en el bloque if user_input:") # Añadido
    st.session_state['chat_history'].append(user_input)
    print("Texto añadido al historial de chat:") # Añadido
    # Generar código con contexto
    generated_text = generate_code_with_context(user_input, st.session_state['chat_history'], st.session_state['code_history'])
    print("Texto generado:", generated_text) # Añadido
    # Extraer el código (si existe)
    generated_code = ""
    if "```python" in generated_text:
        start_index = generated_text.find("```python") + len("```python\n")
        end_index = generated_text.find("```", start_index)
        if end_index != -1:
            generated_code = generated_text[start_index:end_index]
    print("Código generado:", generated_code) # Añadido
    # Mostrar el código o mensaje de respuesta
    with st.chat_message("assistant"):
        if generated_code:
           st.code(generated_code, language="python")
        else:
           st.write(generated_text)
    # Actualizar el historial de código
    st.session_state['code_history'].append(generated_code)
