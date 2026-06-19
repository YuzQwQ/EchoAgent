from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        pass

    def to_dict(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Specific action to perform"},
                        "content": {"type": "string", "description": "Content for the action (e.g. text to write)"}
                    },
                    "required": ["action"]
                }
            }
        }

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        print(f"Tool Registered: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_capabilities_prompt(self) -> str:
        """
        生成注入到 System Prompt 的能力描述
        """
        if not self._tools:
            return ""
            
        prompt = "\n【当前系统已激活的能力模块 (System Capabilities)】\n"
        prompt += "你拥有以下扩展能力，请在回答相关问题时充分利用这些信息建立自我认知：\n"
        for tool in self._tools.values():
            prompt += f"- **{tool.name}**: {tool.description}\n"
        return prompt
