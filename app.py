from xml.etree.ElementTree import TreeBuilder
import openai
from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv
import os
import shelve
import time
import re

load_dotenv()

st.title("Streamlit Chatbot Interface")

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
run_again = True


if run_again:
    vector_store = client.beta.vector_stores.create(name="FAQ Document")
 
    # Ready the files for upload to OpenAI
    file_paths = ["2.txt"]
    file_streams = [open(path, "rb") for path in file_paths]
    
    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id, files=file_streams
    )
    
    # You can print the status and the file counts of the batch to see the result of this operation.
    print(file_batch.status)
    print(file_batch.file_counts)
    
def upload_file(path):  # Upload a file to OpenAI with an "assistants" purpose
    file = client.files.create(
        file=open(path, "rb"),
        purpose="assistants"
    )
    return file

def create_assistant(file): # Create an assistant with OpenAI with instructions and a file to reference
    assistant = client.beta.assistants.create(
        name="Meeting Analyzer",
        instructions="You are a helpful and highly skilled AI assistant trained in language comprehension and summarization. Answer questions about the document provided:",
        tools=[{"type": "file_search"}],
        model="gpt-3.5-turbo",
    )
    assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )
    return assistant

file = upload_file(r'2.txt')
assistant = create_assistant(file)
thread = client.beta.threads.create()

def run_assistant(message_body): # Create a message, run the assistant on it, monitor it for completion, and display the output
    # Create a message in an existing thread
        
    message = client.beta.threads.messages.create(
        thread_id = thread.id,
        role="user",
        content=message_body,
    )

    # Run the existing assistant on the existing thread
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    # Monitor the assistant and report status
    while run.status != "completed":
        run = openai.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        print(run.status)
        time.sleep(2)

    # Extract the messages from the thread
    messages = client.beta.threads.messages.list(
        thread_id=thread.id
    )
    text = ""
    # Display the output
    for message in reversed(messages.data):
       text = message.content[0].text.value
    
    text = re.sub(r'【\d+:\d+†source】', '', text)
    
    return text

# Ensure openai_model is initialized in session state
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"


# Load chat history from shelve file
def load_chat_history():
    with shelve.open("chat_history") as db:
        return db.get("messages", [])


# Save chat history to shelve file
def save_chat_history(messages):
    with shelve.open("chat_history") as db:
        db["messages"] = messages


# Initialize or load chat history
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# Sidebar with a button to delete chat history
with st.sidebar:
    if st.button("Delete Chat History"):
        st.session_state.messages = []
        save_chat_history([])

# Display chat messages
for message in st.session_state.messages:
    avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Main chat interface
if prompt := st.chat_input("How can I help?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        message_placeholder = st.empty()
        full_response = run_assistant(st.session_state["messages"][-1]['content'])
        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})

# Save chat history after each interaction
save_chat_history(st.session_state.messages)
