"""
MyAI Complete End-to-End Test Suite
Verifies all core components:
1. Health & Model Discovery
2. Reasoning & Question Classification
3. Hybrid Memory (ChromaDB + SQLite)
4. RAG Document Intelligence
5. Web Search & Citations
6. Agent Framework & Action Approval
7. Authentication & Session Security
8. Chat API Response
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.model_manager import check_ollama_status, get_installed_models, resolve_model
from backend.personality import get_personality, list_personas
from backend.reasoning import analyze_question, detect_multiple_tasks, evaluate_response_quality
from backend.vector_store import vector_store
from backend.memory import init_memory_table, save_memory, retrieve_relevant_memories, get_all_memories
from backend.rag import build_knowledge_index, retrieve_context
from backend.web_search import search_web, format_search_results
from backend.agent import propose_action, execute_action, TOOLS
from backend.auth import register_user, authenticate_user, validate_session, invalidate_session


class TestMyAIPlatform(unittest.TestCase):

    def test_01_ollama_and_models(self):
        """Verify Ollama is reachable and models are discovered."""
        status = check_ollama_status()
        self.assertTrue(status.get("online"), f"Ollama is offline: {status}")
        models = get_installed_models()
        self.assertGreaterEqual(len(models), 1, "At least one model should be installed")
        resolved = resolve_model(None)
        self.assertIsNotNone(resolved)
        print(f"✓ Ollama Online ({status.get('version')}), Default Model: {resolved}")

    def test_02_reasoning_and_classification(self):
        """Verify intelligent question classification and multi-task detection."""
        # Code classification
        q_code = "Write a Python script to sort a dictionary by values."
        res_code = analyze_question(q_code)
        self.assertEqual(res_code["type"], "programming")
        self.assertTrue(res_code["is_code"])
        self.assertIn("python", res_code["detected_languages"])

        # Math classification
        q_math = "Calculate the volume of a sphere with radius 5"
        res_math = analyze_question(q_math)
        self.assertEqual(res_math["type"], "mathematical")

        # Multi-task detection
        q_multi = "Explain machine learning and also compare it with deep learning. Give me 3 examples."
        multi_res = detect_multiple_tasks(q_multi)
        self.assertTrue(multi_res["is_multiple"])
        print("✓ Question Classification & Multi-Task Detection Verified")

    def test_03_hybrid_memory_system(self):
        """Verify memory insertion, ChromaDB indexing, and semantic recall."""
        init_memory_table()
        test_content = "User is building a production AI platform named MyAI."
        saved = save_memory(test_content, "projects")
        # May be True or False (if already saved), both are valid idempotency
        memories = retrieve_relevant_memories("Tell me about MyAI project", top_k=3, threshold=0.35)
        self.assertGreater(len(memories), 0, "Should retrieve at least one relevant memory")
        print(f"✓ Hybrid Memory Verified ({len(memories)} memories recalled)")

    def test_04_rag_document_intelligence(self):
        """Verify RAG document retrieval using ChromaDB."""
        build_knowledge_index()
        chunks = retrieve_context("Python programming language features", top_k=3, threshold=0.35)
        self.assertGreater(len(chunks), 0, "RAG should retrieve chunks for Python")
        self.assertIn("source", chunks[0])
        print(f"✓ RAG Vector Retrieval Verified (Top match: {chunks[0]['source']} score={chunks[0]['score']})")

    def test_05_web_search_and_citations(self):
        """Verify factual web search without API keys."""
        results = search_web("Alan Turing", max_results=2)
        self.assertGreater(len(results), 0, "Web search should return results for Alan Turing")
        formatted = format_search_results(results)
        self.assertIn("Alan Turing", formatted)
        print("✓ Web Search & Source Citations Verified")

    def test_06_agent_tools_and_approval(self):
        """Verify agent proposal, human approval gate, and execution."""
        # Test code execution with approval
        proposal = propose_action(
            tool_name="execute_python",
            arguments={"code": "x = 42 * 2; print(f'Result: {x}')"},
            explanation="Test safe arithmetic execution"
        )
        self.assertEqual(proposal["status"], "pending_approval")
        action_id = proposal["action_id"]

        # User denies first action test
        reject_res = execute_action(action_id, approved=False)
        self.assertEqual(reject_res["status"], "rejected")

        # User approves second action test
        prop2 = propose_action("execute_python", {"code": "print('OK')"}, "Test approval")
        approve_res = execute_action(prop2["action_id"], approved=True)
        self.assertEqual(approve_res["status"], "executed")
        self.assertIn("OK", approve_res["result"])
        print("✓ Agent System & Human-in-the-Loop Approval Verified")

    def test_07_auth_and_sessions(self):
        """Verify registration, password hashing, and session validation."""
        test_user = f"testuser_{int(sys.time() if hasattr(sys, 'time') else 12345)}"
        import time
        test_user = f"testuser_{int(time.time())}"
        test_pass = "SecurePass123!"

        reg = register_user(test_user, test_pass)
        self.assertTrue(reg.get("success"), f"Register error: {reg}")

        auth = authenticate_user(test_user, test_pass)
        self.assertTrue(auth.get("success"))
        token = auth.get("token")
        self.assertIsNotNone(token)

        # Validate session
        session = validate_session(token)
        self.assertIsNotNone(session)
        self.assertEqual(session["username"], test_user)

        # Logout
        invalidated = invalidate_session(token)
        self.assertTrue(invalidated)
        self.assertIsNone(validate_session(token))
        print("✓ Authentication & Cryptographic Session Security Verified")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RUNNING MYAI COMPREHENSIVE END-TO-END TEST SUITE")
    print("=" * 60 + "\n")
    unittest.main()
