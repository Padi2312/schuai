import os
import signal
import sys
from core.logger import log
from core.conversation import ConversationalAssistant
from server import start_server
import threading


def signal_handler(sig, frame):
    log.info("Keyboard interrupt detected. Exiting...")
    sys.exit(0)


exit_event = threading.Event()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    assistant_thread = threading.Thread(
        target=ConversationalAssistant().conversational_mode, daemon=True
    )
    assistant_thread.start()

    ENABLE_SERVER = os.getenv("ENABLE_SERVER", 0)

    if ENABLE_SERVER:
        log.info("Starting server...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

    while not exit_event.is_set():
        exit_event.wait(1)  # Wait for 1 second or until exit_event is set

    assistant_thread.join()
    if ENABLE_SERVER == "1":
        server_thread.join()