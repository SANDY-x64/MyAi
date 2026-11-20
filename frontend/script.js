
// ============================================
// MyAI - COMPLETE FRONTEND JAVASCRIPT
// ============================================


// --------------------------------------------
// 1. API CONFIGURATION
// --------------------------------------------

const API = "http://127.0.0.1:8000";

const form = document.getElementById("chat-form");
const input = document.getElementById("user-input");
const chatBox = document.getElementById("chat-box");

const conversationList =
    document.getElementById("conversation-list");

const uploadButton =
    document.getElementById("uploadButton");

const pdfInput =
    document.getElementById("pdfInput");

const uploadStatus =
    document.getElementById("uploadStatus");

const documentList =
    document.getElementById("document-list");

const memoryList =
    document.getElementById("memory-list");

const newChatButton =
    document.getElementById("new-chat");

let conversationId =
    localStorage.getItem("myai_conversation_id");

let busy = false;


// --------------------------------------------
// 2. CHAT MESSAGE FUNCTIONS
// --------------------------------------------

function addMessage(message, sender) {

    const div = document.createElement("div");

    div.className = `message ${sender}`;
    div.textContent = message;

    chatBox.appendChild(div);

    chatBox.scrollTop = chatBox.scrollHeight;

    return div;
}


function resetChat() {

    chatBox.innerHTML = "";

    addMessage(
        "Hello! I am MyAI. How can I help?",
        "bot"
    );
}


// --------------------------------------------
// 3. LOAD CONVERSATIONS
// --------------------------------------------

async function loadConversations() {

    const response = await fetch(
        `${API}/conversations`
    );

    if (!response.ok) {
        throw new Error("Could not load conversations");
    }

    const data = await response.json();

    const conversations = data.conversations || [];

    conversationList.innerHTML = "";

    conversations.forEach(chat => {

        const item = document.createElement("div");

        item.className = "chat-item";


        // OPEN BUTTON

        const openButton = document.createElement("button");

        openButton.className = "open-chat";

        openButton.textContent =
            chat.preview || "New conversation";

        openButton.title =
            chat.preview || "Open conversation";

        openButton.addEventListener("click", () => {

            openConversation(chat.conversation_id);

        });


        // DELETE BUTTON

        const deleteButton = document.createElement("button");

        deleteButton.textContent = "×";

        deleteButton.title = "Delete conversation";

        deleteButton.addEventListener("click", () => {

            deleteConversation(chat.conversation_id);

        });


        item.append(openButton, deleteButton);

        conversationList.appendChild(item);

    });

    return conversations;
}


// --------------------------------------------
// 4. OPEN OLD CONVERSATION
// --------------------------------------------

async function openConversation(selectedId) {

    try {

        const response = await fetch(
            `${API}/history/${encodeURIComponent(selectedId)}`
        );

        if (!response.ok) {

            throw new Error(
                `History request failed: ${response.status}`
            );

        }

        const data = await response.json();

        conversationId = selectedId;

        localStorage.setItem(
            "myai_conversation_id",
            selectedId
        );

        chatBox.innerHTML = "";

        data.messages.forEach(message => {

            addMessage(
                message.content,
                message.role === "user" ? "user" : "bot"
            );

        });

    } catch (error) {

        console.error(
            "Open conversation error:",
            error
        );

        alert("Could not open conversation.");

    }

}


// --------------------------------------------
// 5. DELETE CONVERSATION
// --------------------------------------------


async function deleteConversation(selectedId) {

    if (!confirm("Delete this conversation?")) {
        return;
    }

    try {

        const response = await fetch(
            `${API}/conversations/${encodeURIComponent(selectedId)}`,
            {
                method: "DELETE"
            }
        );

        if (!response.ok) {
            throw new Error(
                `Delete failed: ${response.status}`
            );
        }

        if (conversationId === selectedId) {

            conversationId = null;

            localStorage.removeItem(
                "myai_conversation_id"
            );

            resetChat();
        }

        await loadConversations();

    } catch (error) {

        console.error(
            "Delete conversation error:",
            error
        );

        alert("Could not delete conversation.");
    }
}


// --------------------------------------------
// 6. NEW CHAT
// --------------------------------------------

newChatButton.addEventListener("click", () => {

    conversationId = null;

    localStorage.removeItem(
        "myai_conversation_id"
    );

    resetChat();

    input.focus();

});



// --------------------------------------------
// 7. SEND CHAT MESSAGE
// --------------------------------------------

form.addEventListener("submit", async (event) => {

    event.preventDefault();

    if (busy) return;

    const message = input.value.trim();

    if (!message) return;

    busy = true;

    input.disabled = true;

    const button = form.querySelector("button");
    button.disabled = true;

    addMessage(message, "user");

    input.value = "";

    const loading = addMessage("", "bot");

    try {

        // STEP 1: SEND MESSAGE TO STREAMING ENDPOINT

        const response = await fetch(
            `${API}/chat/stream`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    message: message,
                    conversation_id: conversationId
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                `Chat request failed: ${response.status}`
            );
        }

        // STEP 2: GET CONVERSATION ID

        const newConversationId =
            response.headers.get("X-Conversation-ID");

        if (newConversationId) {

            conversationId = newConversationId;

            localStorage.setItem(
                "myai_conversation_id",
                conversationId
            );
        }

        // STEP 3: READ STREAM

        if (!response.body) {
            throw new Error("Streaming is not supported.");
        }

        const reader = response.body.getReader();

        const decoder = new TextDecoder();

        let fullReply = "";

        // STEP 4: DISPLAY EACH CHUNK

        while (true) {

            const { value, done } = await reader.read();

            if (done) break;

            const chunk = decoder.decode(value, {
                stream: true
            });

            fullReply += chunk;

            loading.textContent = fullReply;

            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // STEP 5: FLUSH REMAINING TEXT

        fullReply += decoder.decode();

        loading.textContent = fullReply;

        // STEP 6: REFRESH SIDEBAR DATA

        await loadConversations();

        await loadMemories();

    } catch (error) {

        loading.textContent =
            `MyAI Error: ${error.message || "Something went wrong. Please try again."}`;

        console.error(
            "Chat streaming error:",
            error
        );

    } finally {

        busy = false;

        input.disabled = false;

        button.disabled = false;

        input.focus();

    }

});


// --------------------------------------------
// 8. DOCUMENT UPLOAD
// --------------------------------------------

uploadButton.addEventListener("click", () => {

    pdfInput.click();

});


pdfInput.addEventListener("change", async () => {

    const file = pdfInput.files[0];

    if (!file) return;


    // CHECK FILE FORMAT

    const allowedTypes = [
        ".pdf",
        ".docx"
    ];

    const extension = file.name
        .substring(file.name.lastIndexOf("."))
        .toLowerCase();

    if (!allowedTypes.includes(extension)) {

        uploadStatus.textContent =
            "Only PDF and DOCX files are supported.";

        pdfInput.value = "";

        return;

    }


    // CHECK FILE SIZE

    if (file.size > 10 * 1024 * 1024) {

        uploadStatus.textContent =
            "Document must be smaller than 10 MB.";

        pdfInput.value = "";

        return;

    }


    uploadStatus.textContent =
        "Uploading document...";


    const formData = new FormData();

    formData.append("file", file);


    try {

        const response = await fetch(
            `${API}/upload-document`,
            {
                method: "POST",
                body: formData
            }
        );

        const result = await response.json();

        if (!response.ok) {

            throw new Error(
                result.detail || "Upload failed"
            );

        }

        uploadStatus.textContent =
            "Document uploaded successfully! " +
            result.total_chunks +
            " chunks indexed.";

        await loadDocuments();


    } catch (error) {

        uploadStatus.textContent =
            "Error: " + error.message;

        console.error(
            "Upload error:",
            error
        );


    } finally {

        pdfInput.value = "";

    }

});


// --------------------------------------------
// 9. LOAD DOCUMENTS
// --------------------------------------------

async function loadDocuments() {

    documentList.textContent =
        "Loading documents...";

    try {

        const response = await fetch(
            `${API}/documents`
        );

        if (!response.ok) {

            throw new Error(
                "Could not load documents"
            );

        }

        const result = await response.json();

        documentList.replaceChildren();

        if (
            !result.documents ||
            result.documents.length === 0
        ) {

            documentList.textContent =
                "No documents uploaded.";

            return;

        }


        result.documents.forEach(file => {

            const item = document.createElement("div");

            item.className = "document-item";


            const name = document.createElement("span");

            name.className = "document-name";

            name.textContent = file.filename;


            const deleteButton =
                document.createElement("button");

            deleteButton.className = "delete-document";

            deleteButton.textContent = "Delete";

            deleteButton.addEventListener("click", () => {

                deleteDocument(file.filename);

            });


            item.appendChild(name);

            item.appendChild(deleteButton);

            documentList.appendChild(item);

        });


    } catch (error) {

        documentList.textContent =
            "Unable to load documents.";

        console.error(
            "Document loading error:",
            error
        );

    }

}


// --------------------------------------------
// 10. DELETE DOCUMENT
// --------------------------------------------

async function deleteDocument(filename) {

    const confirmed = confirm(
        "Are you sure you want to delete " +
        filename + "?"
    );

    if (!confirmed) return;


    try {

        const response = await fetch(
            `${API}/documents/${encodeURIComponent(filename)}`,
            {
                method: "DELETE"
            }
        );

        const result = await response.json();

        if (!response.ok) {

            throw new Error(
                result.detail || "Deletion failed"
            );

        }

        alert("Document deleted successfully!");

        await loadDocuments();


    } catch (error) {

        alert("Error: " + error.message);

        console.error(
            "Document deletion error:",
            error
        );

    }

}


// --------------------------------------------
// 11. LOAD LONG-TERM MEMORIES
// --------------------------------------------

async function loadMemories() {

    memoryList.textContent =
        "Loading memories...";

    try {

        const response = await fetch(
            `${API}/memories`
        );

        if (!response.ok) {

            throw new Error(
                "Could not load memories"
            );

        }

        const result = await response.json();

        memoryList.innerHTML = "";

        if (
            !result.memories ||
            result.memories.length === 0
        ) {

            memoryList.textContent =
                "No memories saved yet.";

            return;

        }


        result.memories.forEach(memory => {

            const item = document.createElement("div");

            item.className = "memory-item";


            const details = document.createElement("div");


            const content = document.createElement("div");

            content.className = "memory-content";

            content.textContent = memory.content;


            const category = document.createElement("div");

            category.className = "memory-category";

            category.textContent = memory.category;


            details.appendChild(content);

            details.appendChild(category);


            const deleteButton =
                document.createElement("button");

            deleteButton.className = "delete-memory";

            deleteButton.textContent = "Delete";

            deleteButton.addEventListener("click", () => {

                deleteMemory(memory.id);

            });


            item.appendChild(details);

            item.appendChild(deleteButton);

            memoryList.appendChild(item);

        });


    } catch (error) {

        memoryList.textContent =
            "Unable to load memories.";

        console.error(
            "Memory loading error:",
            error
        );

    }

}


// --------------------------------------------
// 12. DELETE LONG-TERM MEMORY
// --------------------------------------------

async function deleteMemory(memoryId) {

    if (!confirm("Delete this memory?")) {
        return;
    }

    try {

        const response = await fetch(
            `${API}/memories/${memoryId}`,
            {
                method: "DELETE"
            }
        );

        if (!response.ok) {

            throw new Error(
                `Memory deletion failed: ${response.status}`
            );

        }

        await loadMemories();

    } catch (error) {

        alert("Memory deletion failed.");

        console.error(
            "Memory deletion error:",
            error
        );

    }

}


// --------------------------------------------
// 13. START APPLICATION
// --------------------------------------------

async function startApp() {

    resetChat();


    // LOAD CONVERSATIONS

    const conversations = await loadConversations();


    // RESTORE LAST CONVERSATION

    if (conversationId) {

        const exists = conversations.some(
            chat =>
                chat.conversation_id === conversationId
        );

        if (exists) {

            await openConversation(conversationId);

        } else {

            conversationId = null;

            localStorage.removeItem(
                "myai_conversation_id"
            );

        }

    }


    // LOAD DOCUMENTS

    await loadDocuments();


    // LOAD MEMORIES

    await loadMemories();

}


// --------------------------------------------
// 14. RUN APPLICATION
// --------------------------------------------

startApp().catch(error => {

    console.error(
        "MyAI startup error:",
        error
    );

});
