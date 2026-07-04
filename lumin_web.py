import json
import re

import httpx
from ddgs import DDGS

from lumin_config import LuminConfig

WEB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for current information, news, weather, prices, "
                "or facts that require up-to-date data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": (
                "Fetch and read the text content of a web page URL. "
                "Use after web_search when you need more detail from a specific link."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL starting with http:// or https://",
                    }
                },
                "required": ["url"],
            },
        },
    },
]

WEB_TOOL_NAMES = {"web_search", "fetch_webpage"}


def _strip_html(html):
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


class LuminWeb:
    def __init__(self):
        self.enabled = LuminConfig.WEB_SEARCH_ENABLED

    def get_tools(self):
        if self.enabled:
            return WEB_TOOLS
        return None

    def web_search(self, query, max_results=None):
        if not self.enabled:
            return "Web search is disabled."

        query = (query or "").strip()
        if not query:
            return "Search query is empty."

        max_results = max_results or LuminConfig.WEB_SEARCH_MAX_RESULTS
        max_results = max(1, min(max_results, 8))

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as exc:
            return f"Web search failed: {exc}"

        if not results:
            return f"No results found for '{query}'."

        lines = [f"Search results for '{query}':"]
        for index, item in enumerate(results, start=1):
            title = item.get("title", "Untitled")
            body = item.get("body", "")
            href = item.get("href", "")
            lines.append(f"{index}. {title}\n   {body}\n   URL: {href}")

        return "\n".join(lines)

    def fetch_webpage(self, url):
        if not self.enabled:
            return "Web fetch is disabled."

        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            return "Invalid URL. It must start with http:// or https://"

        try:
            response = httpx.get(
                url,
                timeout=LuminConfig.WEB_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": LuminConfig.WEB_USER_AGENT},
            )
            response.raise_for_status()
        except Exception as exc:
            return f"Could not fetch {url}: {exc}"

        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            text = _strip_html(response.text)
        else:
            text = response.text.strip()

        if not text:
            return f"Page fetched but no readable text was found at {url}."

        if len(text) > LuminConfig.WEB_FETCH_MAX_CHARS:
            text = text[: LuminConfig.WEB_FETCH_MAX_CHARS] + "... [truncated]"

        return f"Content from {url}:\n{text}"

    def run_tool(self, tool_call):
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}

        if name == "web_search":
            return self.web_search(args.get("query", ""))
        if name == "fetch_webpage":
            return self.fetch_webpage(args.get("url", ""))
        return f"Unknown web tool: {name}"

    def close(self):
        pass
