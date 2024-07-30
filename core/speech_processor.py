import datetime
import json
import logging
import os
from typing import List

from groq import Groq
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from core.web_scraper import WebSearch


class SpeechProcessor:
    def __init__(self):
        self.client = OpenAI()
        self.speech_to_text_client = Groq()
        self.web_scraper = WebSearch()
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

    def transcribe_audio(self, filename):
        """Transcribe audio using OpenAI's Whisper model."""
        with open(filename, "rb") as file:
            transcription = self.speech_to_text_client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                prompt="Specify context or spelling",
                response_format="json",
            )
        os.remove(filename)
        logging.info(f"Transcription: {transcription.text}")
        return transcription.text

    def process_text_with_openai(self, text):
        """Process text with OpenAI's chat model, maintaining conversation history."""
        self.conversation_history.append({"role": "user", "content": text})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "clear_conversation_history",
                    "description": "Clear the entire conversation history.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "websearch",
                    "description": "Search the internet for the given keywords.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "The keywords or text to search for.",
                            }
                        },
                    },
                },
            },
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.get_system_prompt()}]
            + self.conversation_history,
            tools=tools,
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
            logging.info("Response: %s", response_message.content)
            return response_message.content

    def handle_function_calls(
        self, tool_calls: List[ChatCompletionMessageToolCall], response_message
    ):
        """Handle tool calls from OpenAI response."""
        available_functions = {
            "clear_conversation_history": self.clear_conversation_history,
            "websearch": self.web_scraper.websearch,
        }
        logging.info(f"Found {len(tool_calls)} tool calls.")

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions.get(function_name)
            function_parameters = json.loads(tool_call.function.arguments)

            if function_name == "clear_conversation_history":
                logging.info(f"Conversation history cleared.")
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
            elif function_name == "websearch":
                logging.info(f"Searching the web for '{function_parameters}'...")
                result = function_to_call(function_parameters["keywords"])
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
            else:
                logging.warning(f"Function '{function_name}' not found.")
                return "Function not found."

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        logging.info("Conversation history cleared.")
        return True
