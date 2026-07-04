from lumin_web import WEB_TOOL_NAMES, LuminWeb


class LuminToolRouter:
    def __init__(self, web_helper=None):
        self.web = web_helper or LuminWeb()

    def get_tools(self):
        return self.web.get_tools() if self.web else None

    def run_tool(self, tool_call):
        name = tool_call.function.name
        if name in WEB_TOOL_NAMES and self.web:
            return self.web.run_tool(tool_call)
        return f"Unknown tool: {name}"

    def close(self):
        if self.web:
            self.web.close()
