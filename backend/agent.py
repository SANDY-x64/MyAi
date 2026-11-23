"""
MyAI Autonomous Agent & Tool Calling Framework
Decomposes complex goals into sequential tasks, selects and executes tools,
and enforces human-in-the-loop approval for file modifications and code execution.
"""

import uuid
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.web_search import search_web, fetch_webpage_content, format_search_results
from backend.rag import retrieve_context
from backend.memory import retrieve_relevant_memories
from backend.model_manager import resolve_model, OLLAMA_BASE_URL
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


class ToolDefinition(BaseModel):
    name: str
    description: str
    requires_approval: bool
    parameters: Dict[str, Any]


class ActionProposal(BaseModel):
    action_id: str
    tool_name: str
    arguments: Dict[str, Any]
    explanation: str
    status: str = "pending"  # pending, approved, rejected, executed
    result: Optional[str] = None


# In-memory store for pending agent actions awaiting human approval
PENDING_ACTIONS: Dict[str, Dict[str, Any]] = {}


# ----------------------------------------------------
# TOOL IMPLEMENTATIONS
# ----------------------------------------------------

def tool_web_search(query: str) -> str:
    """Search the web for up-to-date facts and sources."""
    results = search_web(query, max_results=4)
    return format_search_results(results)


def tool_fetch_webpage(url: str) -> str:
    """Fetch text from a specific web URL."""
    res = fetch_webpage_content(url)
    if res.get("success"):
        return f"Webpage content from {url}:\n\n{res.get('content', '')}"
    return f"Failed to fetch webpage: {res.get('error', 'unknown error')}"


def tool_rag_search(query: str) -> str:
    """Search uploaded document knowledge in ChromaDB."""
    chunks = retrieve_context(query, top_k=4)
    if not chunks:
        return "No relevant document knowledge found."
    formatted = [f"Source: {c['source']} (Relevance: {c['score']})\n{c['text']}" for c in chunks]
    return "\n\n".join(formatted)


def tool_recall_memory(query: str) -> str:
    """Search saved long-term user memories."""
    memories = retrieve_relevant_memories(query, top_k=5)
    if not memories:
        return "No relevant user memories found."
    return "\n".join([f"- [{m['category']}] {m['content']} (score: {m['score']})" for m in memories])


def tool_read_file(filename: str) -> str:
    """Read a file from the workspace or knowledge folder."""
    # Check workspace first
    target = WORKSPACE_DIR / filename
    if not target.exists():
        target = BASE_DIR / "knowledge" / filename

    if not target.exists() or not target.is_file():
        return f"Error: File '{filename}' not found."

    try:
        content = target.read_text(encoding="utf-8", errors="ignore")
        return f"Content of '{filename}':\n\n{content}"
    except Exception as exc:
        return f"Error reading file '{filename}': {exc}"


def tool_write_file(filename: str, content: str) -> str:
    """Create or overwrite a file in the workspace directory (Requires Approval)."""
    # Enforce workspace isolation
    safe_filename = Path(filename).name
    target = WORKSPACE_DIR / safe_filename
    try:
        target.write_text(content, encoding="utf-8")
        return f"Successfully saved file to workspace: '{safe_filename}' ({len(content)} characters)."
    except Exception as exc:
        return f"Error writing file '{safe_filename}': {exc}"


def tool_execute_python(code: str) -> str:
    """Execute Python code in an isolated subprocess with timeout (Requires Approval)."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(WORKSPACE_DIR)
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if result.returncode != 0:
            return f"Execution Failed (Exit {result.returncode}):\n{error or output}"
        return f"Execution Output:\n{output if output else '[Code completed with no output]'}"
    except subprocess.TimeoutExpired:
        return "Execution Error: Code timed out after 15 seconds."
    except Exception as exc:
        return f"Execution Error: {exc}"


# ----------------------------------------------------
# TOOL REGISTRY
# ----------------------------------------------------

TOOLS = {
    "web_search": {
        "function": tool_web_search,
        "requires_approval": False,
        "description": "Search the web for up-to-date information, facts, news, and references."
    },
    "fetch_webpage": {
        "function": tool_fetch_webpage,
        "requires_approval": False,
        "description": "Fetch text from a specific webpage URL."
    },
    "rag_search": {
        "function": tool_rag_search,
        "requires_approval": False,
        "description": "Retrieve information from uploaded user documents and PDFs in ChromaDB."
    },
    "recall_memory": {
        "function": tool_recall_memory,
        "requires_approval": False,
        "description": "Search long-term memory for user preferences, background, and goals."
    },
    "read_file": {
        "function": tool_read_file,
        "requires_approval": False,
        "description": "Read content from a workspace file."
    },
    "write_file": {
        "function": tool_write_file,
        "requires_approval": True,
        "description": "Write or edit a file in the workspace. Requires user confirmation."
    },
    "execute_python": {
        "function": tool_execute_python,
        "requires_approval": True,
        "description": "Run a Python script in an isolated process. Requires user confirmation."
    }
}


# ----------------------------------------------------
# ACTION PROPOSAL & HUMAN-IN-THE-LOOP APPROVAL
# ----------------------------------------------------

def propose_action(tool_name: str, arguments: Dict[str, Any], explanation: str) -> Dict[str, Any]:
    """Create a proposed action requiring human review."""
    action_id = str(uuid.uuid4())
    proposal = {
        "action_id": action_id,
        "tool_name": tool_name,
        "arguments": arguments,
        "explanation": explanation,
        "status": "pending_approval"
    }
    PENDING_ACTIONS[action_id] = proposal
    return proposal


def execute_action(action_id: str, approved: bool = True) -> Dict[str, Any]:
    """Execute an approved action or record user rejection."""
    proposal = PENDING_ACTIONS.get(action_id)
    if not proposal:
        return {"success": False, "error": "Action not found or expired."}

    if not approved:
        proposal["status"] = "rejected"
        proposal["result"] = "Action was denied by user."
        return {"success": True, "status": "rejected", "result": proposal["result"]}

    tool_name = proposal["tool_name"]
    args = proposal["arguments"]
    tool_entry = TOOLS.get(tool_name)

    if not tool_entry:
        proposal["status"] = "failed"
        proposal["result"] = f"Tool '{tool_name}' does not exist."
        return {"success": False, "error": proposal["result"]}

    try:
        func = tool_entry["function"]
        result = func(**args)
        proposal["status"] = "executed"
        proposal["result"] = result
        return {"success": True, "status": "executed", "result": result}
    except Exception as exc:
        proposal["status"] = "failed"
        proposal["result"] = f"Tool execution failed: {exc}"
        return {"success": False, "error": str(exc)}


def get_pending_actions() -> List[Dict[str, Any]]:
    """Return all actions currently awaiting user review."""
    return [act for act in PENDING_ACTIONS.values() if act["status"] == "pending_approval"]


# ----------------------------------------------------
# AGENT DECOMPOSITION & EXECUTION
# ----------------------------------------------------

def plan_and_execute_agent_task(user_goal: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Deconstructs user goal into planned steps, executes safe read-only tools,
    and returns either a final response or proposed actions requiring approval.
    """
    target_model = resolve_model(model)
    lower_goal = user_goal.lower()

    # Detect if web search is directly needed
    web_results = None
    if any(k in lower_goal for k in ["search", "latest", "news", "who is", "what is", "current", "weather"]):
        web_results = tool_web_search(user_goal)

    # Detect if RAG document search is relevant
    doc_results = tool_rag_search(user_goal)
    if "No relevant document knowledge found" in doc_results:
        doc_results = None

    # Detect if memory recall is relevant
    memory_results = tool_recall_memory(user_goal)
    if "No relevant user memories found" in memory_results:
        memory_results = None

    # Check if user explicitly asked to write a file
    if any(k in lower_goal for k in ["save this file", "write a file", "create a file called", "save to"]):
        # Extract filename heuristic
        filename = "output.txt"
        words = user_goal.split()
        for i, w in enumerate(words):
            if w in ["called", "named", "to"] and i + 1 < len(words):
                filename = words[i + 1].strip("'\".,")
                break

        proposal = propose_action(
            tool_name="write_file",
            arguments={"filename": filename, "content": f"# Generated by MyAI\n# Task: {user_goal}\n"},
            explanation=f"Create file '{filename}' in workspace for the requested task."
        )
        return {
            "mode": "action_required",
            "plan": [
                f"1. User requested file creation '{filename}'.",
                "2. Action proposal created with safety boundary.",
                "3. Awaiting user approval."
            ],
            "pending_action": proposal
        }

    return {
        "mode": "completed",
        "web_context": web_results,
        "doc_context": doc_results,
        "memory_context": memory_results
    }
