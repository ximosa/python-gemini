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
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  name TEXT UNIQUE,
                                  date TEXT
                            )""")
        self.conn.commit()
        # Inicializar chat actual:
        if 'selected_chat_id' not in st.session_state:
            self.cursor.execute("SELECT id, name FROM chats ORDER BY id DESC LIMIT 1")
            last_chat = self.cursor.fetchone()
            if last_chat:
              st.session_state['selected_chat_id'] = last_chat[0]
              st.session_state['selected_chat_name'] = last_chat[1]
            else:
              st.session_state['selected_chat_id'] = 1
              st.session_state['selected_chat_name'] = "Chat 1"
              self.add_chat(st.session_state['selected_chat_name'])


    def add_message(self, speaker, message):
         now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
         self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS chat_{st.session_state['selected_chat_id']} (
                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  date TEXT,
                                  speaker TEXT,
                                  message TEXT
                            )""")
         self.cursor.execute(f"INSERT INTO chat_{st.session_state['selected_chat_id']} (date, speaker, message) VALUES (?, ?, ?)", (now, speaker, message))
         self.conn.commit()

    def get_all_chats(self):
         self.cursor.execute("SELECT name, id FROM chats")
         return self.cursor.fetchall()

    def get_history(self):
      self.cursor.execute(f"SELECT speaker, message FROM chat_{st.session_state['selected_chat_id']}")
      return self.cursor.fetchall()


    def add_chat(self, name):
      now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      self.cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (name, now))
      self.conn.commit()
      st.session_state['selected_chat_id'] = self.cursor.lastrowid
      st.session_state['selected_chat_name'] = name


    def delete_chat(self, id):
      self.cursor.execute(f"DROP TABLE IF EXISTS chat_{id}")
      self.cursor.execute("DELETE FROM chats WHERE id=?", (id,))
      self.conn.commit()
      # Restablecer el chat seleccionado si se borra el actual
      if st.session_state.get('selected_chat_id') == id:
          st.session_state['selected_chat_id'] = None
          st.session_state['selected_chat_name'] = None
          # Seleccionar otro chat o crear uno nuevo si no quedan chats
          remaining_chats = self.get_all_chats()
          if remaining_chats:
              st.session_state['selected_chat_id'] = remaining_chats[0][1]
              st.session_state['selected_chat_name'] = remaining_chats[0][0]
          else:
              self.add_chat("Chat 1") # Crear un nuevo chat si no hay ninguno


    def close(self):
        # NO CERRAR LA CONEXIÓN AQUÍ. Se cierra al final de la app
        pass




# --- Función para generar respuesta --- (Igual que antes)
def generate_response(prompt, chat_history, custom_prompt):
 # ... (Código igual que antes)


# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")

# Inicializamos el chat como un objeto FUERA del ciclo de reruns
if 'chat' not in st.session_state:
    st.session_state['chat'] = Chat()
chat = st.session_state['chat']



custom_prompt = st.text_area("Instrucciones adicionales para la IA (opcional):", value = st.session_state.get('custom_prompt',""))
st.session_state['custom_prompt'] = custom_prompt

# --- Layout de la Interfaz ---
with st.sidebar:
    st.header("Chats")
    all_chats = chat.get_all_chats()
    
    if all_chats:
        for chat_name, chat_id in all_chats:
            col1, col2 = st.columns([3, 1]) # Dividir en dos columnas
            with col1:
                if st.button(chat_name, key=f"select_{chat_id}"):
                    st.session_state['selected_chat_id'] = chat_id
                    st.session_state['selected_chat_name'] = chat_name
            with col2: # Botón de borrar en la segunda columna
                if st.button("❌", key=f"delete_{chat_id}"):
                    chat.delete_chat(chat_id)
                    st.rerun() # Recargar la página

        st.button("Nuevo Chat", on_click=lambda: chat.add_chat(f"Chat {len(all_chats) + 1}")) # Agregar nuevo chat

    else:
        st.button("Nuevo Chat", on_click=lambda: chat.add_chat("Chat 1"))


# ... (resto del código igual que antes)



# Cerrar la conexión al salir de la app
try:
  # Resto del código de la app
  user_input = st.chat_input("Escribe tu mensaje aquí:", key=f'chat_input_{st.session_state.get("selected_chat_id", 0)}')
   # ... (Lógica del chat - igual que antes) ...
finally:
    chat.conn.close()
