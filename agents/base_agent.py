import os
import json
from typing import List, Dict, Any, Callable
from openai import AzureOpenAI
import agents.prompts as pmt
from agents.tools import airline_agent_tools, car_agent_tools

AGENTS_CONFIG = {
    "airline": {
        "name": "Airline Assistant",
        "id": "airline",
        "system_prompt": pmt.airline_agent_prompt,
        "tools": airline_agent_tools,
        "voice_id": {
            "es": "UOIqAnmS11Reiei1Ytkc", # Carolina
            "en": "56AoDkrOh6qfVPDXZ7Pt" # Cassidy
        }
    },
    "car_rental": {
        "name": "Car Rental Assistant",
        "id": "car_rental",
        "system_prompt": pmt.car_rental_prompt,
        "tools": car_agent_tools,
        "voice_id": {
            "es": "7ilYbYb99yBZGMUUKSaf", # Alex
            "en": "UgBBYS2sOqTuMpoF3BR0" # Mark
        }
    }
}

PRESET_AUDIOS = {
    "airline": {
        "en": "transfer_air_to_car_en.wav",
        "es": "transfer_air_to_car_es.wav",
    },
    "car_rental": {
        "en": "transfer_car_to_air_en.wav",
        "es": "transfer_car_to_air_es.wav",
    },
}

class BaseAgent:
    def __init__(
        self, 
        initial_agent: str, # initial_agent: key in AGENTS_CONFIG ('airline' or 'car_rental')
        deployment_name: str = "gpt-4o",
        language: str = "es"
        ):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        self.deployment_name = deployment_name
        self.registered_tools: Dict[str, Callable[..., Any]] = {}
        self.tool_definitions: List[Dict[str, Any]] = []
        self.set_agent(initial_agent, language)

    def set_agent(self, agent_key: str, language: str) -> None:
        cfg = AGENTS_CONFIG[agent_key]
        self.name = cfg["name"]
        self.system_prompt = cfg["system_prompt"]
        self.voice_id = cfg["voice_id"][language]
        self.id = cfg["id"]
        self._load_tools(cfg["tools"])
        self.clear_history()

    def _load_tools(self, tools_list: List[Any]) -> None:
        self.registered_tools.clear()
        self.tool_definitions.clear()
        for definition, func in tools_list:
            self.registered_tools[definition["name"]] = func
            self.tool_definitions.append({
                "type": "function",
                "function": definition
            })

    def clear_history(self) -> None:
        self.conversation_history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def add_message(self, role: str, content: str, **kwargs) -> None:
        msg = {"role": role, "content": content}
        msg.update(kwargs)
        self.conversation_history.append(msg)

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        func = self.registered_tools.get(name)
        if not func:
            return f"Tool '{name}' not found."
        result = func(**arguments)
        if name == "transfer_agent":
            return result
        return json.dumps(result) if isinstance(result, dict) else str(result)

    def generate_response(self, user_input: str):
        self.add_message("user", user_input)

        while True:
            # first model call (may request tools)
            resp = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=self.conversation_history,
                tools=self.tool_definitions,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            content = msg.content or ""

            if content:
                yield (content, self.voice_id)

            if not msg.tool_calls:
                # no more tools: record and break
                self.add_message("assistant", content)
                break

            # record partial assistant reply with tool metadata
            self.add_message(
                "assistant",
                content,
                tool_calls=[{
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in msg.tool_calls]
            )

            # execute each requested tool
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                out = self.execute_tool(name, args)

                if name == "transfer_agent":
                    # in-flight switch to new agent
                    ctx = out["context"]
                    lang = out.get("language", "es")
                    target = out.get("target_agent", "car_rental")
                    auth_state = out.get("auth_state", "User is not authenticated")
                    current = self.id
                    self.set_agent(target, lang)

                    system_message = f"{'Speak in Spanish' if lang == 'es' else 'Speak in English'}.\n{auth_state}.\n<Context>\n{ctx}\n</Context>"
                    self.add_message("system", system_message)
                    if not content:
                        yield ("transfer_agent", PRESET_AUDIOS[current][lang])
                    yield ("transition", "smooth_beep.wav")
                else:
                    self.add_message("tool", out, tool_call_id=tc.id)

    def get_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history
