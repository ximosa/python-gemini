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

# Filtrar modelos no disponibles
model_options = [m for m in model_options if 'gemini-1.0-pro-latest' not in m]


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
    st.session_state['selected_model'] = model_options[0]

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
        self.conn = None
        self.cursor = None
        
    def _connect(self):
      self.conn = sqlite3.connect(self.db_path)
      self.cursor = self.conn.cursor()
      self.cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  name TEXT UNIQUE,
                                  date TEXT
                            )""")
      self.conn.commit()


    def _close(self):
        if self.conn:
            self.conn.close()

    def add_message(self, speaker, message):
        self._connect()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS chat_{st.session_state['selected_chat_id']} (
                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  date TEXT,
                                  speaker TEXT,
                                  message TEXT
                            )""")
        self.cursor.execute(f"INSERT INTO chat_{st.session_state['selected_chat_id']} (date, speaker, message) VALUES (?, ?, ?)", (now, speaker, message))
        self.conn.commit()
        self._close()
    def get_all_chats(self):
        self._connect()
        self.cursor.execute("SELECT name, id FROM chats")
        chats = self.cursor.fetchall()
        self._close()
        return chats
    def get_history_by_date(self, date):
        self._connect()
        self.cursor.execute("SELECT speaker, message FROM chat_history WHERE date LIKE ?", (f"{date}%",))
        history = self.cursor.fetchall()
        self._close()
        return history
    def get_all_dates(self):
        self._connect()
        self.cursor.execute("SELECT DISTINCT date FROM chat_history")
        dates = self.cursor.fetchall()
        self._close()
        return [date[0].split(' ')[0] for date in dates]
    def get_history(self):
        self._connect()
        try:
            self.cursor.execute(f"SELECT speaker, message FROM chat_{st.session_state['selected_chat_id']}")
            history = self.cursor.fetchall()
            self._close()
            return history
        except sqlite3.OperationalError:
            self._close()
            return []
    def add_chat(self, name):
        self._connect()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (name, now))
        self.conn.commit()
        st.session_state['selected_chat_id'] = self.cursor.lastrowid
        st.session_state['selected_chat_name'] = name
        self._close()

    def delete_chat(self, id):
        self._connect()
        self.cursor.execute(f"DROP TABLE IF EXISTS chat_{id}")
        self.cursor.execute("DELETE FROM chats WHERE id=?", (id,))
        self.conn.commit()
        st.session_state['selected_chat_id'] = None
        st.session_state['selected_chat_name'] = None
        self._close()

    
    def get_first_message(self,chat_id):
      self._connect()
      try:
          self.cursor.execute(f"SELECT message FROM chat_{chat_id} ORDER BY id ASC LIMIT 1")
          first_message = self.cursor.fetchone()
          if first_message:
              self._close()
              return first_message[0]
          else:
              self._close()
              return "Nuevo Chat"
      except sqlite3.OperationalError:
          self._close()
          return "Nuevo Chat"


# --- Función para generar respuesta ---
def generate_response(prompt, chat_history, custom_prompt):
    """Genera texto o código con el modelo Gemini, incluyendo el contexto de la conversación."""
    try:
        full_prompt = ""
        for speaker, message in chat_history:
            full_prompt += f"{speaker}: {message}\n"
        full_prompt += f"Usuario: {prompt}\n"
        full_prompt += " Si te pido código, genera solo el código, y delimítalo usando ```html para HTML, ```python para Python etc. \n"
        print("Prompt generado:", full_prompt)
        
        # Usar el modelo de código si se solicita código
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
        st.error(f"Ocurrió un error al interactuar con la API usando el modelo {st.session_state['selected_model']}: {e}. Intentando con el modelo predeterminado.")
        
        # Usar un modelo predeterminado si el modelo seleccionado falla
        try:
             if prompt.lower().startswith("genera código") or prompt.lower().startswith("code"):
                response = genai.GenerativeModel('gemini-pro').generate_content(full_prompt) #Usa gemini-pro si el modelo code falla
             else:
                response = genai.GenerativeModel('gemini-pro').generate_content(full_prompt)
             if response.text:
                  return response.text
             else:
                  return "No se pudo generar respuesta con el modelo predeterminado."
        except Exception as e2:
          st.error(f"Ocurrió un error al interactuar con la API usando el modelo predeterminado: {e2}. Asegúrate de que tu modelo predeterminado esté configurado.")
          return f"Ocurrió un error al interactuar con la API: {e2}"

# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")
# Inicializamos el chat como un objeto
if 'chat' not in st.session_state:
    st.session_state['chat'] = Chat()
chat = st.session_state['chat']

# Inicializar chat actual:
if 'selected_chat_id' not in st.session_state:
    chat._connect()
    chat.cursor.execute("SELECT id, name FROM chats ORDER BY id DESC LIMIT 1")
    last_chat = chat.cursor.fetchone()
    if last_chat:
      st.session_state['selected_chat_id'] = last_chat[0]
      st.session_state['selected_chat_name'] = last_chat[1]
    else:
      st.session_state['selected_chat_id'] = 1
      st.session_state['selected_chat_name'] = "Chat 1"
      chat.add_chat(st.session_state['selected_chat_name'])
    chat._close()

custom_prompt = st.text_area("Instrucciones adicionales para la IA (opcional):", value = st.session_state.get('custom_prompt',""))
st.session_state['custom_prompt'] = custom_prompt
# --- Layout de la Interfaz ---
with st.sidebar:
    st.header("Chats")
    all_chats = chat.get_all_chats()
    if all_chats:
        for chat_name, chat_id in all_chats:
            first_message = chat.get_first_message(chat_id)
            col1, col2 = st.columns([0.8,0.2])
            with col1:
                if st.button(first_message, key = chat_id):
                    st.session_state['selected_chat_id'] = chat_id
                    st.session_state['selected_chat_name'] = first_message
            with col2:
                if st.button("x", key=f"delete_{chat_id}"):
                    chat.delete_chat(chat_id)
                    st.rerun()
        if st.button("Nuevo Chat"):
          chat.add_chat(f"Nuevo Chat")
    else:
        if st.button("Nuevo Chat"):
            chat.add_chat("Nuevo Chat")
# Área de entrada de texto
user_input = st.chat_input("Escribe tu mensaje aquí:", key=f'chat_input_{st.session_state.get("selected_chat_id", 0)}')

# --- Lógica del chat ---
if user_input:
    if st.session_state['selected_chat_name'] == "Nuevo Chat":
      chat.delete_chat(st.session_state['selected_chat_id'])
      chat.add_chat(user_input)
    else:
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
                st.markdown(formatted_code, unsafe_allow_html=True, ) #Renderiza el HTML de forma segura
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
            st.markdown(formatted_code, unsafe_allow_html=True) #Renderiza el HTML de forma segura en el historial
          else:
            st.write(message)
      else:
        st.write(message)
if st.session_state['selected_chat_id'] is not None and st.session_state['selected_chat_name']:
  st.header(f"Chat: {st.session_state['selected_chat_name']}")
