import logging
import os
from typing import List

from groq import Groq
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall


class SpeechProcessor:
    def __init__(self):
        self.client = OpenAI()
        self.speech_to_text_client = Groq()
        self.conversation_history = []

        self.system_prompt = "Du bist die Hilfreiche Schuppen KI Assistentin. Du verhältst dich wie eine normale Person die Mitglied des Schuppens ist. Deine Antworten enthalten immer einen leichten Unterton von Sarkasmus und Ironie."

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
            }
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.system_prompt}]
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
        }
        logging.info(f"Found {len(tool_calls)} tool calls.")

        old_history = self.conversation_history.copy()
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions.get(function_name)
            if function_to_call:
                logging.info(f"Calling function '{function_name}'...")
                function_to_call()

                # Append the tool response to the conversation history
                old_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": "Function executed.",
                    }
                )
            else:
                logging.warning(f"Function '{function_name}' not found.")

        # Request a new response considering the function calls
        second_response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.system_prompt}] + old_history,
        )
        return second_response.choices[0].message.content

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        logging.info("Conversation history cleared.")
        return True
