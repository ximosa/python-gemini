import streamlit as st
import google.generativeai as genai
import os
import sqlite3
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from datetime import datetime

# --- Configuración de la API ---
API_KEY = st.secrets["API_KEY"]
if not API_KEY:
    st.error("No se encontró la clave de API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)

available_models = genai.list_models()
model_options = [m.name for m in available_models if 'generateContent' in m.supported_generation_methods]

if 'selected_model' not in st.session_state:
    if 'gemini-pro' in model_options:
      st.session_state['selected_model'] = 'gemini-pro'
    elif model_options:
      st.session_state['selected_model'] = model_options[0]
    else:
        st.error("No se encontró ningún modelo válido para la API")
        st.stop()

try:
    selected_model_name = st.selectbox("Selecciona un modelo:", model_options, index = model_options.index(st.session_state['selected_model']))
    st.session_state['selected_model'] = selected_model_name
except Exception as e:
    st.error(f"Ocurrió un error al seleccionar el modelo: {e}. Seleccionando modelo por defecto: {model_options[0]}")
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


# --- Funciones auxiliares ---
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
# --- Clase Chat ---
class Chat:
    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS chat_history (
                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  date TEXT,
                                  speaker TEXT,
                                  message TEXT
                            )""")
        self.conn.commit()

    def add_message(self, speaker, message):
         now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
         self.cursor.execute("INSERT INTO chat_history (date, speaker, message) VALUES (?, ?, ?)", (now, speaker, message))
         self.conn.commit()

    def get_history_by_date(self, date):
        self.cursor.execute("SELECT speaker, message FROM chat_history WHERE date LIKE ?", (f"{date}%",))
        return self.cursor.fetchall()
    def get_all_dates(self):
        self.cursor.execute("SELECT DISTINCT date FROM chat_history")
        dates = self.cursor.fetchall()
        return [date[0].split(' ')[0] for date in dates]


    def get_history(self):
      self.cursor.execute("SELECT speaker, message FROM chat_history")
      return self.cursor.fetchall()


    def close(self):
        self.conn.close()

# --- Función para generar respuesta ---
def generate_response(prompt, chat_history, custom_prompt):
    """Genera texto o código con el modelo Gemini, incluyendo el contexto de la conversación."""
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
custom_prompt = st.text_area("Instrucciones adicionales para la IA (opcional):", value = st.session_state.get('custom_prompt',""))
st.session_state['custom_prompt'] = custom_prompt
# --- Layout de la Interfaz ---
col1, col2 = st.columns([3, 1])


with col1:
    # Área de entrada de texto
    user_input = st.chat_input("Escribe tu mensaje aquí:")

    # --- Lógica del chat ---
    if user_input:
      chat.add_message("Usuario", user_input)
      # Generar respuesta con contexto
      generated_text = generate_response(user_input, chat.get_history(), custom_prompt)
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
with col2:
    st.subheader("Historial del chat")
    dates = chat.get_all_dates()
    selected_date = st.sidebar.selectbox("Selecciona una fecha:", dates) if dates else None
    if selected_date:
      history = chat.get_history_by_date(selected_date)
      for speaker, message in history:
         with st.chat_message(speaker.lower()):
           if is_code(message):
              formatted_code = format_code(message)
              if formatted_code:
                  st.markdown(formatted_code, unsafe_allow_html=True)
              else:
                 st.write(message)
           else:
               st.write(message)

chat.close()
