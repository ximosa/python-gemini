import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
import os
import uuid

# --- Configuración de la API ---
API_KEY = st.secrets.get("API_KEY")
if not API_KEY:
    st.error("No se encontró la clave de la API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)

# --- Obtener modelos disponibles y filtrar ---
available_models = genai.list_models()
model_options = [
    m.name for m in available_models
    if 'generateContent' in m.supported_generation_methods
    and 'deprecated' not in m.name.lower()
    and not m.name.lower().endswith('-latest')
    and m.name not in ['gemini-pro-vision'] #Excluir gemini-pro-vision por que no funciona en chat
]

if 'selected_model' not in st.session_state:
    if 'gemini-pro' in model_options:
        st.session_state['selected_model'] = 'gemini-pro'
    elif model_options:
        st.session_state['selected_model'] = model_options[0]
    else:
        st.error("No se encontró ningún modelo válido para la API")
        st.stop()

try:
    selected_model_name = st.selectbox("Selecciona un modelo:", model_options, index=model_options.index(st.session_state['selected_model']))
    st.session_state['selected_model'] = selected_model_name
except Exception as e:
    st.error(f"Ocurrió un error al seleccionar el modelo: {e}. Seleccionando modelo por defecto: {model_options[0]}")
    selected_model_name = model_options[0]
    st.session_state['selected_model'] = selected_model_name

model = genai.GenerativeModel(selected_model_name)

# Modelo para código
code_model_name = None
for m in available_models:
    if 'code' in m.name.lower() and 'generateContent' in m.supported_generation_methods and 'deprecated' not in m.name.lower():
        code_model_name = m.name
        break

if code_model_name:
    code_model = genai.GenerativeModel(code_model_name)
    print(f"Usando modelo para código: {code_model_name}")
else:
    code_model = model
    print("No se encontró un modelo específico para código, usando el modelo por defecto")

# --- Clase Chat ---
class Chat:
    def __init__(self, db_path="chat_history.db", upload_dir="uploads"):
        self.db_path = db_path
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)
        self._create_main_table()
        self._initialize_chat()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_main_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT UNIQUE,
                                    date TEXT
                                )""")
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al crear la tabla 'chats': {e}")
            conn.rollback()
        finally:
            conn.close()

    def _initialize_chat(self):
      conn = self._get_connection()
      cursor = conn.cursor()
      try:
        cursor.execute("SELECT id, name FROM chats ORDER BY id DESC LIMIT 1")
        last_chat = cursor.fetchone()
        if last_chat:
            st.session_state['selected_chat_id'] = last_chat[0]
            st.session_state['selected_chat_name'] = last_chat[1]
            self._add_chat_table(st.session_state['selected_chat_id']) #Crea tabla si ya existe chat
        else:
          st.session_state['selected_chat_id'] = 1
          st.session_state['selected_chat_name'] = "Chat 1"
          self._add_chat_table(st.session_state['selected_chat_id']) #Crea la tabla para el chat inicial
      except sqlite3.Error as e:
          st.error(f"Error al inicializar el chat: {e}")
          st.session_state['selected_chat_id'] = 1
          st.session_state['selected_chat_name'] = "Chat 1"
          self._add_chat_table(st.session_state['selected_chat_id']) #Crea la tabla para el chat inicial
      finally:
        conn.close()

    def _add_chat_table(self, chat_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS chat_{chat_id} (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    date TEXT,
                                    speaker TEXT,
                                    message TEXT,
                                    file_path TEXT
                                    )""")
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al crear la tabla del chat {chat_id}: {e}")
            conn.rollback()
        finally:
            conn.close()


    def add_message(self, speaker, message, file_path=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute(f"INSERT INTO chat_{st.session_state['selected_chat_id']} (date, speaker, message, file_path) VALUES (?, ?, ?, ?)", (now, speaker, message, file_path))
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al añadir el mensaje: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_all_chats(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name, id FROM chats")
            chats = cursor.fetchall()
            return chats
        except sqlite3.Error as e:
            st.error(f"Error al obtener chats: {e}")
            return []
        finally:
            conn.close()

    def get_history(self):
        if not st.session_state.get('selected_chat_id'):
            return []
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT id, speaker, message, file_path FROM chat_{st.session_state['selected_chat_id']}")
            history = cursor.fetchall()
            return history
        except sqlite3.Error as e:
            st.error(f"Error al obtener el historial del chat: {e}")
            return []
        finally:
            conn.close()
    
    def delete_message(self, message_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DELETE FROM chat_{st.session_state['selected_chat_id']} WHERE id=?", (message_id,))
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al eliminar el mensaje: {e}")
            conn.rollback()
        finally:
            conn.close()

    def add_chat(self, name):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (name, now))
            conn.commit()
            chat_id = cursor.lastrowid
            st.session_state['selected_chat_id'] = chat_id
            st.session_state['selected_chat_name'] = name
            self._add_chat_table(chat_id)
        except sqlite3.Error as e:
            st.error(f"Error al añadir un nuevo chat: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def create_chat_with_first_message(self, first_message):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (first_message[:50] , now)) #Guardar el nombre del chat con la primera pregunta
            conn.commit()
            chat_id = cursor.lastrowid
            st.session_state['selected_chat_id'] = chat_id
            st.session_state['selected_chat_name'] = first_message[:50]  # Usa la primera pregunta como nombre del chat
            self._add_chat_table(chat_id)
        except sqlite3.Error as e:
            st.error(f"Error al añadir un nuevo chat: {e}")
            conn.rollback()
        finally:
            conn.close()


    def delete_chat(self, id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS chat_{id}")
            cursor.execute("DELETE FROM chats WHERE id=?", (id,))
            conn.commit()
            st.session_state['selected_chat_id'] = None
            st.session_state['selected_chat_name'] = None
        except sqlite3.Error as e:
            st.error(f"Error al eliminar el chat: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def upload_file(self, uploaded_file):
        if uploaded_file:
            file_extension = os.path.splitext(uploaded_file.name)[1]
            file_name = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(self.upload_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
            return file_path
        return None

# --- Función para generar respuesta ---
def generate_response(prompt, chat_history):
    try:
        full_prompt = ""
        for _, speaker, message, _ in chat_history:
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

# Inicializamos el chat como un objeto
if 'chat' not in st.session_state:
    st.session_state['chat'] = Chat()
chat = st.session_state['chat']

# --- Layout de la interfaz ---
with st.sidebar:
    st.header("Chats")
    all_chats = chat.get_all_chats()
    if all_chats:
        for chat_name, chat_id in all_chats:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                if st.button(chat_name, key=f"chat_{chat_id}", use_container_width=True):
                    st.session_state['selected_chat_id'] = chat_id
                    st.session_state['selected_chat_name'] = chat_name
            with col2:
                if st.button("🗑️", key=f"delete_{chat_id}", use_container_width=True):
                    chat.delete_chat(chat_id)
                    st.rerun()
        if st.button("Nuevo Chat"):
            st.session_state['creating_new_chat'] = True
    else:
        if st.button("Nuevo Chat"):
             st.session_state['creating_new_chat'] = True

# Área de entrada de texto y adjuntos
col1, col2 = st.columns([0.8, 0.2])
with col1:
    user_input = st.chat_input("Escribe tu mensaje aquí:", key=f'chat_input_{st.session_state.get("selected_chat_id", 0)}')
with col2:
    uploaded_file = st.file_uploader("Adjuntar archivo", key=f'file_uploader_{st.session_state.get("selected_chat_id", 0)}')

# Lógica del chat
if user_input or uploaded_file:
    file_path = chat.upload_file(uploaded_file)
    if st.session_state.get('creating_new_chat', False):
        chat.create_chat_with_first_message(user_input)
        st.session_state['creating_new_chat'] = False
    chat.add_message("Usuario", user_input, file_path)
    generated_text = generate_response(user_input, chat.get_history())
    chat.add_message("Assistant", generated_text)
    print("Texto generado:", generated_text)

    # Mostrar la respuesta
    with st.chat_message("assistant"):
        st.write(generated_text)


# Mostrar el historial del chat
for message_id, speaker, message, file_path in chat.get_history():
    with st.chat_message(speaker):
        if message:
            st.write(message)
        if file_path:
            st.markdown(f'<a href="{file_path}" download>Descargar archivo adjunto</a>', unsafe_allow_html=True)
        if speaker == "Usuario":
            if st.button("Eliminar", key=f"delete_message_{message_id}", use_container_width=True):
                chat.delete_message(message_id)
                st.rerun()

if st.session_state['selected_chat_id'] is not None and st.session_state['selected_chat_name']:
    st.header(f"Chat: {st.session_state['selected_chat_name']}")
