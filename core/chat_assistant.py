import yaml
import datetime
import json
from typing import List

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from config import load_config
from core.logger import log
from core.tools import Tools


class ChatAssistant:
    def __init__(self):
        self.client = OpenAI()
        self.tools = Tools(
            additional_tools={
                "clear_conversation_history": self.clear_conversation_history,
            }
        )
        self.conversation_history = []
        self.system_prompt = load_config()["system_prompt"]

    def get_system_prompt(self):
        current_date = datetime.datetime.now()
        current_date = current_date.strftime("%Y-%m-%d %H:%M:%S")
        self.system_prompt = load_config()["system_prompt"]
        return self.system_prompt + f"\nCurrent date and time: {current_date}"

    def process_text_with_openai(self, text):
        """Process text with OpenAI's chat model, maintaining conversation history."""
        self.conversation_history.append({"role": "user", "content": text})
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.get_system_prompt()}]
            + self.conversation_history,
            tools=self.tools.get_tools_json(),
            temperature=0.7,
            tool_choice="auto",
        )
        log.debug(
            "Prompt History: %s",
            [{"role": "system", "content": self.get_system_prompt()}]
            + self.conversation_history,
        )

        response_message = response.choices[0].message
        tool_calls: List[ChatCompletionMessageToolCall] | None = (
            response_message.tool_calls
        )

        if tool_calls:
            # Append the tool response to the conversation history
            self.conversation_history.append(response_message)
            answer = self.handle_function_calls(tool_calls, response_message)
            # json.dump(self.conversation_history, open("logs/history.log", "w"))
            return answer
        else:
            self.conversation_history.append(
                {"role": "assistant", "content": response_message.content}
            )
            log.info("Response: %s", response_message.content)
            # json.dump(self.conversation_history, open("logs/history.log", "w"))
            return response_message.content

    def handle_function_calls(
        self, tool_calls: List[ChatCompletionMessageToolCall], response_message
    ):
        """Handle tool calls from OpenAI response."""
        available_functions = self.tools.available_tools()
        log.info(f"Found {len(tool_calls)} tool calls.")

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions.get(function_name)
            function_parameters = json.loads(tool_call.function.arguments)
            if function_to_call is None:
                log.warning(f"Function '{function_name}' not found.")
                return "Function not found."

            if function_name == "clear_conversation_history":
                log.info(f"Conversation history cleared.")
                old_history = self.conversation_history.copy()
                function_to_call()
                old_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": "Function executed.",
                    }
                )
                second_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": self.get_system_prompt()}]
                    + old_history,
                )
                return second_response.choices[0].message.content
            else:
                log.info(
                    f"Executing function '{function_name}' with parameters: {function_parameters}"
                )
                result = function_to_call(function_parameters)
                self.conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(result),
                    }
                )
                second_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": self.get_system_prompt()}]
                    + self.conversation_history,
                )
                return second_response.choices[0].message.content

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        log.info("Conversation history cleared.")
        return True
