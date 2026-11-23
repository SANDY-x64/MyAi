"""
MyAI Web Intelligence Engine
Provides live web knowledge search, encyclopedic fact retrieval, and URL scraping.
Does not require external paid API keys.
"""

import requests
import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote, unquote

HEADERS = {
    "User-Agent": "MyAIAssistant/1.0 (Personal Local AI Assistant; https://github.com/myai)"
}


def search_wikipedia(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Query Wikipedia Search API for authoritative factual information and sources."""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "utf8": 1,
            "format": "json"
        }
        res = requests.get(url, params=params, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            search_items = data.get("query", {}).get("search", [])
            results = []
            for item in search_items[:max_results]:
                title = item.get("title", "")
                snippet_raw = item.get("snippet", "")
                # Clean HTML tags from snippet
                snippet = re.sub(r'<[^>]+>', '', snippet_raw).strip()
                page_url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"

                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": page_url,
                    "source": "Wikipedia"
                })
            return results
    except Exception as exc:
        print(f"[WebSearch] Wikipedia error: {exc}")
    return []


def search_duckduckgo_instant(query: str) -> List[Dict[str, str]]:
    """Query DuckDuckGo Instant Answer API for quick definitions and topics."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        res = requests.get(url, params=params, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            abstract = data.get("AbstractText", "").strip()
            source_url = data.get("AbstractURL", "").strip()
            source_name = data.get("AbstractSource", "DuckDuckGo")

            results = []
            if abstract:
                results.append({
                    "title": f"{query.title()} Overview",
                    "snippet": abstract,
                    "link": source_url or "https://duckduckgo.com",
                    "source": source_name
                })

            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and "Text" in topic:
                    text = topic.get("Text", "")
                    link = topic.get("FirstURL", "")
                    if text and link:
                        results.append({
                            "title": link.split("/")[-1].replace("_", " "),
                            "snippet": text,
                            "link": link,
                            "source": "DuckDuckGo"
                        })
            return results
    except Exception as exc:
        print(f"[WebSearch] DDG Instant error: {exc}")
    return []


def fetch_webpage_content(url: str, max_chars: int = 3000) -> Dict[str, Any]:
    """Fetch and extract readable text from a specific webpage URL."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return {"success": False, "error": f"HTTP {res.status_code}"}

        html = res.text
        # Strip script, style, nav, footer
        cleaned = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        # Strip all HTML tags
        text = re.sub(r'<[^>]+>', ' ', cleaned)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return {
            "success": True,
            "url": url,
            "content": text[:max_chars]
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def search_web(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Unified web search function.
    Combines encyclopedic search with instant facts.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # 1. Search Wikipedia
    results = search_wikipedia(cleaned_query, max_results=max_results)

    # 2. Add DDG Instant answers
    if len(results) < max_results:
        ddg_hits = search_duckduckgo_instant(cleaned_query)
        for hit in ddg_hits:
            if not any(r["link"] == hit["link"] for r in results):
                results.append(hit)

    return results[:max_results]


def format_search_results(results: List[Dict[str, str]]) -> str:
    """Format search results into a clean markdown reference block for LLM prompt context."""
    if not results:
        return "No web search results available."

    formatted = ["WEB SEARCH RESULTS (Use these sources to cite information):"]
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[{i}] {r['title']} ({r.get('source', 'Web')})\n"
            f"Source URL: {r['link']}\n"
            f"Summary: {r['snippet']}\n"
        )
    return "\n".join(formatted)
