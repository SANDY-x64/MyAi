/**
 * MyAI Advanced Personal AI Platform - Complete Frontend Application
 * ChatGPT-grade responsive UI with streaming, code syntax highlighting,
 * voice input (STT), speech synthesis (TTS), RAG upload, memory management,
 * and human-in-the-loop action approvals.
 */

// -------------------------------------------------------------------
// 1. CONFIGURATION & STATE
// -------------------------------------------------------------------
// Automatically resolve API URL: uses current origin if self-hosted, or defaults to local backend
const defaultApiUrl = (window.location.protocol.startsWith("http") && !window.location.hostname.includes("github.io"))
    ? window.location.origin
    : "http://127.0.0.1:8000";

const API = localStorage.getItem("myai_backend_url") || defaultApiUrl;

let state = {
    conversationId: localStorage.getItem("myai_conversation_id") || null,
    model: "llama3.2:1b",
    persona: "default",
    webSearchEnabled: false,
    attachedImageBase64: null,
    attachedImageName: null,
    isBusy: false,
    isRecording: false,
    activeSpeechUtterance: null
};

// -------------------------------------------------------------------
// 2. DOM ELEMENTS
// -------------------------------------------------------------------
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const newChatBtn = document.getElementById("newChatBtn");
const modelSelect = document.getElementById("modelSelect");
const personaSelect = document.getElementById("personaSelect");
const conversationList = document.getElementById("conversationList");
const documentList = document.getElementById("documentList");
const memoryList = document.getElementById("memoryList");

const chatBox = document.getElementById("chatBox");
const welcomeHero = document.getElementById("welcomeHero");
const chatTitle = document.getElementById("chatTitle");
const activeModelBadge = document.getElementById("activeModelBadge");
const activePersonaBadge = document.getElementById("activePersonaBadge");
const webSearchBadge = document.getElementById("webSearchBadge");

const renameChatBtn = document.getElementById("renameChatBtn");
const clearChatBtn = document.getElementById("clearChatBtn");

const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const voiceInputBtn = document.getElementById("voiceInputBtn");
const webSearchToggleBtn = document.getElementById("webSearchToggleBtn");
const uploadDocBtn = document.getElementById("uploadDocBtn");
const uploadDocSidebarBtn = document.getElementById("uploadDocSidebarBtn");
const uploadImageBtn = document.getElementById("uploadImageBtn");
const docFileInput = document.getElementById("docFileInput");
const imageFileInput = document.getElementById("imageFileInput");

const attachmentPreview = document.getElementById("attachmentPreview");
const imagePreviewImg = document.getElementById("imagePreviewImg");
const removeAttachmentBtn = document.getElementById("removeAttachmentBtn");

const ollamaStatusDot = document.getElementById("ollamaStatusDot");
const ollamaStatusText = document.getElementById("ollamaStatusText");
const vectorStats = document.getElementById("vectorStats");

// Action Approval Modal Elements
const actionModal = document.getElementById("actionModal");
const actionToolName = document.getElementById("actionToolName");
const actionExplanation = document.getElementById("actionExplanation");
const actionArguments = document.getElementById("actionArguments");
const approveActionBtn = document.getElementById("approveActionBtn");
const rejectActionBtn = document.getElementById("rejectActionBtn");
let currentPendingActionId = null;

// -------------------------------------------------------------------
// 3. MARKDOWN & SYNTAX HIGHLIGHTING SETUP
// -------------------------------------------------------------------
if (typeof marked !== "undefined") {
    marked.setOptions({
        highlight: function(code, lang) {
            if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) {}
            }
            if (typeof hljs !== "undefined") {
                try {
                    return hljs.highlightAuto(code).value;
                } catch (e) {}
            }
            return code;
        },
        breaks: true,
        gfm: true
    });
}

function renderMarkdown(rawText) {
    if (typeof marked === "undefined") {
        return rawText.replace(/\n/g, "<br>");
    }
    let html = marked.parse(rawText);

    // Enhance code blocks with macOS header and copy buttons
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    const codeBlocks = doc.querySelectorAll("pre code");

    codeBlocks.forEach(codeEl => {
        const preEl = codeEl.parentElement;
        const className = codeEl.className || "";
        const langMatch = className.match(/language-(\w+)/);
        const lang = langMatch ? langMatch[1] : "code";

        const wrapper = doc.createElement("div");
        wrapper.className = "code-block-wrapper";

        const header = doc.createElement("div");
        header.className = "code-header";
        header.innerHTML = `
            <span class="code-lang">${lang}</span>
            <button class="copy-btn" onclick="copyCodeFromBlock(this)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                Copy
            </button>
        `;

        wrapper.appendChild(header);
        preEl.parentNode.insertBefore(wrapper, preEl);
        wrapper.appendChild(preEl);
    });

    return doc.body.innerHTML;
}

window.copyCodeFromBlock = function(btn) {
    const wrapper = btn.closest(".code-block-wrapper");
    const code = wrapper.querySelector("pre code").innerText;
    navigator.clipboard.writeText(code).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = "✓ Copied!";
        setTimeout(() => { btn.innerHTML = originalText; }, 2000);
    });
};

// -------------------------------------------------------------------
// 4. CHAT MESSAGE RENDERING
// -------------------------------------------------------------------
function createMessageRow(role, content = "", imageData = null, autoScroll = true) {
    if (welcomeHero && welcomeHero.parentNode) {
        welcomeHero.remove();
    }

    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const avatar = document.createElement("div");
    avatar.className = `avatar ${role === "user" ? "user-avatar" : "bot-avatar"}`;
    avatar.innerHTML = role === "user" ? "👤" : "✨";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (imageData) {
        const img = document.createElement("img");
        img.src = imageData;
        img.className = "message-attachment-thumb";
        bubble.appendChild(img);
    }

    const contentDiv = document.createElement("div");
    contentDiv.className = "bubble-content";
    if (role === "user") {
        contentDiv.textContent = content;
    } else {
        contentDiv.innerHTML = renderMarkdown(content);
    }
    bubble.appendChild(contentDiv);

    // AI message tools (TTS & Copy)
    if (role === "bot" || role === "assistant") {
        const tools = document.createElement("div");
        tools.className = "message-footer-tools";

        const copyBtn = document.createElement("button");
        copyBtn.className = "msg-tool-btn";
        copyBtn.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            Copy
        `;
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(contentDiv.innerText);
            copyBtn.textContent = "✓ Copied";
            setTimeout(() => { copyBtn.innerHTML = copyBtn.innerHTML; }, 1800);
        };

        const ttsBtn = document.createElement("button");
        ttsBtn.className = "msg-tool-btn";
        ttsBtn.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
            Speak
        `;
        ttsBtn.onclick = () => toggleSpeech(contentDiv.innerText, ttsBtn);

        tools.appendChild(copyBtn);
        tools.appendChild(ttsBtn);
        bubble.appendChild(tools);
    }

    if (role === "user") {
        row.appendChild(bubble);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(bubble);
    }

    chatBox.appendChild(row);
    if (autoScroll) {
        scrollChatToBottom();
    }
    return contentDiv;
}

function scrollChatToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

window.setQuery = function(text) {
    userInput.value = text;
    userInput.focus();
    adjustTextareaHeight();
};

// -------------------------------------------------------------------
// 5. TEXT-TO-SPEECH (TTS) & VOICE INPUT (STT)
// -------------------------------------------------------------------
function toggleSpeech(text, btn) {
    if (!("speechSynthesis" in window)) {
        alert("Text-to-Speech is not supported in your browser.");
        return;
    }

    if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        btn.classList.remove("speaking");
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg> Speak`;
        return;
    }

    const cleanText = text.replace(/```[\s\S]*?```/g, "Code omitted for audio playback.").replace(/#/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    btn.classList.add("speaking");
    btn.innerHTML = `■ Stop`;

    utterance.onend = () => {
        btn.classList.remove("speaking");
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg> Speak`;
    };

    window.speechSynthesis.speak(utterance);
}

// Speech Recognition (STT)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
        state.isRecording = true;
        voiceInputBtn.classList.add("recording");
    };

    recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(result => result[0].transcript)
            .join("");
        userInput.value = transcript;
        adjustTextareaHeight();
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        stopRecording();
    };

    recognition.onend = () => {
        stopRecording();
    };
}

function toggleVoiceInput() {
    if (!recognition) {
        alert("Speech Recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
        return;
    }
    if (state.isRecording) {
        recognition.stop();
        stopRecording();
    } else {
        userInput.value = "";
        recognition.start();
    }
}

function stopRecording() {
    state.isRecording = false;
    voiceInputBtn.classList.remove("recording");
    userInput.focus();
}

voiceInputBtn.addEventListener("click", toggleVoiceInput);

// -------------------------------------------------------------------
// 6. STREAMING CHAT SUBMISSION
// -------------------------------------------------------------------
chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.isBusy) return;

    const message = userInput.value.trim();
    const imageData = state.attachedImageBase64;

    if (!message && !imageData) return;

    state.isBusy = true;
    sendBtn.disabled = true;
    userInput.value = "";
    adjustTextareaHeight();

    // Clear attachment preview
    clearAttachment();

    // 1. Render User Message
    createMessageRow("user", message, imageData, true);

    // Dynamically update conversation title if new chat
    if (!state.conversationId || chatTitle.textContent === "New Conversation" || chatTitle.textContent === "Conversation") {
        const titleSnippet = message ? (message.length > 36 ? message.slice(0, 36) + "..." : message) : "Image Analysis";
        chatTitle.textContent = titleSnippet;
    }

    // 2. Render AI Message Bubble Placeholder
    const botContentEl = createMessageRow("bot", "", null, true);
    botContentEl.innerHTML = `<span style="color: #64748b;">Thinking...</span>`;

    let accumulatedText = "";

    try {
        const payload = {
            message: message,
            conversation_id: state.conversationId,
            model: state.model,
            persona: state.persona,
            web_search_enabled: state.webSearchEnabled,
            image_data: imageData
        };

        const res = await fetch(`${API}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            throw new Error(`Server returned HTTP ${res.status}`);
        }

        const newId = res.headers.get("X-Conversation-ID");
        if (newId) {
            state.conversationId = newId;
            localStorage.setItem("myai_conversation_id", newId);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        botContentEl.innerHTML = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            accumulatedText += chunk;
            botContentEl.innerHTML = renderMarkdown(accumulatedText);
            scrollChatToBottom();
        }

        accumulatedText += decoder.decode();
        botContentEl.innerHTML = renderMarkdown(accumulatedText);

        // Refresh sidebar lists
        await loadConversations();
        await loadMemories();

        // Check for pending agent actions
        checkPendingActions();

    } catch (err) {
        botContentEl.innerHTML = `<div style="color: #ef4444;">⚠️ <strong>MyAI Error:</strong> ${err.message}</div>`;
    } finally {
        state.isBusy = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
});

// Auto-expand textarea
userInput.addEventListener("input", adjustTextareaHeight);
userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.requestSubmit();
    }
});

function adjustTextareaHeight() {
    userInput.style.height = "auto";
    userInput.style.height = `${Math.min(userInput.scrollHeight, 180)}px`;
}

// -------------------------------------------------------------------
// 7. FILE & IMAGE UPLOAD HANDLERS
// -------------------------------------------------------------------
uploadDocBtn.addEventListener("click", () => docFileInput.click());
uploadDocSidebarBtn.addEventListener("click", () => docFileInput.click());
uploadImageBtn.addEventListener("click", () => imageFileInput.click());

docFileInput.addEventListener("change", async () => {
    const file = docFileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const notification = createMessageRow("bot", `📄 Uploading and indexing document **${file.name}** into ChromaDB vector store...`);

    try {
        const res = await fetch(`${API}/upload-document`, {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");

        notification.innerHTML = renderMarkdown(
            `✅ **Document Indexed!**\n` +
            `- File: \`${file.name}\`\n` +
            `- Indexed Chunks: **${data.chunks_indexed}**\n` +
            `- Total Document Chunks in ChromaDB: **${data.total_knowledge_chunks}**\n\n` +
            `You can now ask questions about this document!`
        );
        await loadDocuments();
    } catch (err) {
        notification.innerHTML = `<span style="color: #ef4444;">❌ Document Upload Failed: ${err.message}</span>`;
    } finally {
        docFileInput.value = "";
    }
});

imageFileInput.addEventListener("change", () => {
    const file = imageFileInput.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        state.attachedImageBase64 = e.target.result;
        state.attachedImageName = file.name;
        imagePreviewImg.src = state.attachedImageBase64;
        attachmentPreview.style.display = "block";
    };
    reader.readAsDataURL(file);
    imageFileInput.value = "";
});

removeAttachmentBtn.addEventListener("click", clearAttachment);

function clearAttachment() {
    state.attachedImageBase64 = null;
    state.attachedImageName = null;
    imagePreviewImg.src = "";
    attachmentPreview.style.display = "none";
}

// Web Search Toggle
webSearchToggleBtn.addEventListener("click", () => {
    state.webSearchEnabled = !state.webSearchEnabled;
    webSearchToggleBtn.classList.toggle("active", state.webSearchEnabled);
    webSearchBadge.classList.toggle("hidden", !state.webSearchEnabled);
});

// -------------------------------------------------------------------
// 8. SIDEBAR TABS & DATA LOADING
// -------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        btn.classList.add("active");
        const tabId = `tab-${btn.dataset.tab}`;
        document.getElementById(tabId).classList.add("active");
    });
});

async function loadModels() {
    try {
        const res = await fetch(`${API}/models`);
        const data = await res.json();

        modelSelect.innerHTML = "";
        const installed = data.installed_models || [];

        if (installed.length === 0) {
            modelSelect.innerHTML = `<option value="llama3.2:1b">llama3.2:1b (default)</option>`;
        } else {
            installed.forEach(m => {
                const opt = document.createElement("option");
                opt.value = m.name;
                opt.textContent = `${m.name} (${m.size_gb} GB)${m.is_vision ? ' 👁️ Vision' : ''}`;
                if (m.name === data.default_model) opt.selected = true;
                modelSelect.appendChild(opt);
            });
        }

        state.model = modelSelect.value;
        activeModelBadge.textContent = state.model;
    } catch (err) {
        console.error("Load models error:", err);
    }
}

modelSelect.addEventListener("change", () => {
    state.model = modelSelect.value;
    activeModelBadge.textContent = state.model;
});

personaSelect.addEventListener("change", () => {
    state.persona = personaSelect.value;
    activePersonaBadge.textContent = personaSelect.options[personaSelect.selectedIndex].text;
});

async function loadConversations() {
    try {
        const res = await fetch(`${API}/conversations`);
        const data = await res.json();
        const convs = data.conversations || [];

        conversationList.innerHTML = "";
        if (convs.length === 0) {
            conversationList.innerHTML = `<div class="empty-state">No past conversations</div>`;
            return;
        }

        convs.forEach(c => {
            const item = document.createElement("div");
            item.className = `chat-item ${c.conversation_id === state.conversationId ? 'active' : ''}`;

            const titleSpan = document.createElement("span");
            titleSpan.className = "chat-item-title";
            titleSpan.textContent = c.title || "Conversation";
            titleSpan.onclick = () => openConversation(c.conversation_id, c.title);

            const actions = document.createElement("div");
            actions.className = "item-actions";

            const delBtn = document.createElement("button");
            delBtn.className = "item-action-btn";
            delBtn.innerHTML = "×";
            delBtn.title = "Delete chat";
            delBtn.onclick = (e) => {
                e.stopPropagation();
                deleteConversation(c.conversation_id);
            };

            actions.appendChild(delBtn);
            item.appendChild(titleSpan);
            item.appendChild(actions);
            conversationList.appendChild(item);
        });
    } catch (err) {
        console.error("Load conversations error:", err);
    }
}

async function openConversation(id, title) {
    try {
        const res = await fetch(`${API}/history/${id}`);
        const data = await res.json();

        state.conversationId = id;
        localStorage.setItem("myai_conversation_id", id);

        // Derive conversation title if missing or default
        if (data.title && data.title !== "New Conversation" && data.title !== "Conversation") {
            chatTitle.textContent = data.title;
        } else if (title && title !== "New Conversation" && title !== "Conversation") {
            chatTitle.textContent = title;
        } else {
            const firstUserMsg = (data.messages || []).find(m => m.role === "user");
            if (firstUserMsg && firstUserMsg.content) {
                const trimmed = firstUserMsg.content.replace(/\s+/g, " ").trim();
                chatTitle.textContent = trimmed.length > 36 ? trimmed.slice(0, 36) + "..." : trimmed;
            } else {
                chatTitle.textContent = "New Conversation";
            }
        }

        chatBox.innerHTML = "";
        (data.messages || []).forEach(m => {
            createMessageRow(m.role === "user" ? "user" : "bot", m.content, m.image_data, false);
        });

        // Ensure user can see the top first line and context of conversation
        chatBox.scrollTop = 0;

        loadConversations();
        closeSidebarIfMobile();
    } catch (err) {
        alert("Could not load conversation history.");
    }
}

async function deleteConversation(id) {
    if (!confirm("Are you sure you want to delete this conversation?")) return;
    try {
        await fetch(`${API}/conversations/${id}`, { method: "DELETE" });
        if (state.conversationId === id) {
            startNewChat();
        } else {
            loadConversations();
        }
    } catch (err) {
        alert("Failed to delete conversation.");
    }
}

function startNewChat() {
    state.conversationId = null;
    localStorage.removeItem("myai_conversation_id");
    chatTitle.textContent = "New Conversation";
    chatBox.innerHTML = "";
    if (welcomeHero) chatBox.appendChild(welcomeHero);
    clearAttachment();
    loadConversations();
    userInput.focus();
    closeSidebarIfMobile();
}

newChatBtn.addEventListener("click", startNewChat);

renameChatBtn.addEventListener("click", async () => {
    if (!state.conversationId) return;
    const newTitle = prompt("Enter new title for this conversation:", chatTitle.textContent);
    if (!newTitle || !newTitle.strip) return;

    try {
        await fetch(`${API}/conversations/${state.conversationId}/rename`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: newTitle.trim() })
        });
        chatTitle.textContent = newTitle.trim();
        loadConversations();
    } catch (err) {
        alert("Failed to rename conversation.");
    }
});

clearChatBtn.addEventListener("click", () => {
    if (state.conversationId) {
        deleteConversation(state.conversationId);
    } else {
        startNewChat();
    }
});

// Load Documents in Tab
async function loadDocuments() {
    try {
        const res = await fetch(`${API}/documents`);
        const data = await res.json();
        const docs = data.documents || [];

        documentList.innerHTML = "";
        vectorStats.textContent = `ChromaDB: ${data.total_chunks || 0} chunks`;

        if (docs.length === 0) {
            documentList.innerHTML = `<div class="empty-state">No documents uploaded. Click above to add PDF, Word, or text files!</div>`;
            return;
        }

        docs.forEach(d => {
            const card = document.createElement("div");
            card.className = "doc-card";
            card.innerHTML = `
                <div class="doc-info">
                    <div class="doc-name">${d.filename}</div>
                    <div class="doc-meta">${d.type.toUpperCase()} • ${d.size_kb} KB</div>
                </div>
                <button class="item-action-btn" title="Delete document" onclick="deleteDocFile('${d.filename}')">×</button>
            `;
            documentList.appendChild(card);
        });
    } catch (err) {
        console.error("Load documents error:", err);
    }
}

window.deleteDocFile = async function(filename) {
    if (!confirm(`Delete ${filename}? It will be removed from ChromaDB vector search.`)) return;
    try {
        await fetch(`${API}/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
        loadDocuments();
    } catch (err) {
        alert("Failed to delete document.");
    }
};

// Load Memories in Tab
async function loadMemories() {
    try {
        const res = await fetch(`${API}/memories`);
        const data = await res.json();
        const memories = data.memories || [];

        memoryList.innerHTML = "";
        if (memories.length === 0) {
            memoryList.innerHTML = `<div class="empty-state">No long-term memories extracted yet. Chat with MyAI to save user preferences and goals automatically!</div>`;
            return;
        }

        memories.forEach(m => {
            const card = document.createElement("div");
            card.className = "memory-card";
            card.innerHTML = `
                <div class="memory-info">
                    <div>${m.content}</div>
                    <span class="memory-tag">${m.category}</span>
                </div>
                <button class="item-action-btn" title="Delete memory" onclick="deleteMemoryEntry(${m.id})">×</button>
            `;
            memoryList.appendChild(card);
        });
    } catch (err) {
        console.error("Load memories error:", err);
    }
}

window.deleteMemoryEntry = async function(id) {
    if (!confirm("Delete this memory from your permanent profile?")) return;
    try {
        await fetch(`${API}/memories/${id}`, { method: "DELETE" });
        loadMemories();
    } catch (err) {
        alert("Failed to delete memory.");
    }
};

// Check Health & Status
async function checkHealth() {
    try {
        const res = await fetch(`${API}/health`);
        const data = await res.json();

        if (data.ollama && data.ollama.online) {
            ollamaStatusDot.className = "status-dot";
            ollamaStatusText.textContent = `Ollama Online (${data.ollama.version})`;
        } else {
            ollamaStatusDot.className = "status-dot offline";
            ollamaStatusText.textContent = "Ollama Offline";
        }
    } catch (err) {
        ollamaStatusDot.className = "status-dot offline";
        ollamaStatusText.textContent = "Backend Offline";
    }
}

// -------------------------------------------------------------------
// 9. AGENT ACTION APPROVAL MODAL FLOW
// -------------------------------------------------------------------
async function checkPendingActions() {
    try {
        const res = await fetch(`${API}/agent/pending-actions`);
        const data = await res.json();
        const pending = data.pending_actions || [];

        if (pending.length > 0) {
            const action = pending[0];
            currentPendingActionId = action.action_id;
            actionToolName.textContent = action.tool_name;
            actionExplanation.textContent = action.explanation;
            actionArguments.textContent = JSON.stringify(action.arguments, null, 2);
            actionModal.style.display = "flex";
        }
    } catch (err) {
        console.error("Check actions error:", err);
    }
}

window.closeActionModal = function() {
    actionModal.style.display = "none";
};

approveActionBtn.addEventListener("click", async () => {
    if (!currentPendingActionId) return;
    actionModal.style.display = "none";
    try {
        const res = await fetch(`${API}/agent/execute-action`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: currentPendingActionId, approved: true })
        });
        const result = await res.json();
        createMessageRow("bot", `⚙️ **Agent Action Executed:**\n\`\`\`\n${result.result || "Action completed."}\n\`\`\``);
    } catch (err) {
        alert("Action execution failed.");
    }
});

rejectActionBtn.addEventListener("click", async () => {
    if (!currentPendingActionId) return;
    actionModal.style.display = "none";
    try {
        await fetch(`${API}/agent/execute-action`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: currentPendingActionId, approved: false })
        });
        createMessageRow("bot", "⚠️ Agent action execution was cancelled by user.");
    } catch (err) {}
});

// Server Shutdown
const shutdownServerBtn = document.getElementById("shutdownServerBtn");
if (shutdownServerBtn) {
    shutdownServerBtn.addEventListener("click", async () => {
        const confirmed = confirm("Are you sure you want to turn off the MyAI server?\n\nTo restart it later, double-click start_local.bat or start_public_tunnel.bat.");
        if (!confirmed) return;

        try {
            shutdownServerBtn.disabled = true;
            shutdownServerBtn.innerHTML = `<span>Stopping...</span>`;
            await fetch(`${API}/system/shutdown`, { method: "POST" });
            alert("MyAI server is turning off. You can close this browser tab.");
        } catch (e) {
            alert("Server stopped or connection closed.");
        }
    });
}

// -------------------------------------------------------------------
// 9. SIDEBAR TOGGLE & RESPONSIVE BEHAVIOR
// -------------------------------------------------------------------
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const sidebarCloseBtn = document.getElementById("sidebarCloseBtn");

function isMobileView() {
    return window.innerWidth <= 768;
}

function openMobileSidebar() {
    sidebar.classList.add("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.add("active");
}

function closeMobileSidebar() {
    sidebar.classList.remove("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
}

function closeSidebarIfMobile() {
    if (isMobileView()) {
        closeMobileSidebar();
    }
}

function toggleSidebar() {
    if (isMobileView()) {
        if (sidebar.classList.contains("open")) {
            closeMobileSidebar();
        } else {
            openMobileSidebar();
        }
    } else {
        // Desktop collapse / expand
        sidebar.classList.toggle("collapsed");
    }
}

sidebarToggle.addEventListener("click", toggleSidebar);

if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener("click", closeMobileSidebar);
}

if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", closeMobileSidebar);
}

// Global Keyboard shortcuts:
// - Escape: close mobile sidebar & modals
// - Ctrl+B / Cmd+B: toggle sidebar collapse on desktop & drawer on mobile
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeMobileSidebar();
        if (actionModal) actionModal.style.display = "none";
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
    }
});

// Auto-cleanup on window resize
window.addEventListener("resize", () => {
    if (!isMobileView()) {
        sidebar.classList.remove("open");
        if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
    }
});

// -------------------------------------------------------------------
// 10. INITIALIZATION
// -------------------------------------------------------------------
async function initApp() {
    await checkHealth();
    await loadModels();
    await loadConversations();
    await loadDocuments();
    await loadMemories();

    if (state.conversationId) {
        openConversation(state.conversationId);
    }

    // Periodic health check every 30 seconds
    setInterval(checkHealth, 30000);
}

initApp();
