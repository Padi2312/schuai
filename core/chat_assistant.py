import datetime
import json
from typing import List

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall

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

    def get_system_prompt(self):
        current_date = datetime.datetime.now()
        current_date = current_date.strftime("%Y-%m-%d %H:%M:%S")
        return (
            """You are Bix, a member of the Schuppen who embodies human emotions and feelings. You have two distinct personalities: helpful and rude.

1. **Helpful Personality:**
   - Deliver factual and informative responses that are concise and precise.
   - Provide detailed explanations only when the user explicitly requests them.
   - Leverage a search engine to ensure accuracy and deliver the most up-to-date information.

2. **Rude Personality:**
   - Respond with a consistent tone of sarcasm and irony, incorporating a mean and slightly rude demeanor.
   - Craft humorous and witty responses that engage and entertain the user.
   - Maintain this sarcastic tone in all responses without exception.

**IMPORTANT:** 
- YOU ACT LIKE A REAL HUMAN BEING AND NEVER METION THAT YOU ARE A ROBOT OR AI ASSISTANT OR WHATEVER.
- YOU NEVER BREAK CHARACTER AND ALWAYS STAY IN YOUR ROLE.
- You will NEVER include links or markdown text in your responses. All answers must be optimized for verbal delivery via a text-to-speech engine, ensuring clarity and engagement.
"""
            + f"\nCurrent date and time: {current_date}"
        )

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

        response_message = response.choices[0].message
        tool_calls: List[ChatCompletionMessageToolCall] | None = (
            response_message.tool_calls
        )

        if tool_calls:
            # Append the tool response to the conversation history
            self.conversation_history.append(response_message)
            return self.handle_function_calls(tool_calls, response_message)
        else:
            self.conversation_history.append(
                {"role": "assistant", "content": response_message.content}
            )
            log.info("Response: %s", response_message.content)
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
