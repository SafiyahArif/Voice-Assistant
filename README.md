# Voice-Activated Personal Assistant (Python)

A simple but extensible voice assistant that can:
- Listen to your voice (or accept typed input if no mic is found)
- Speak responses out loud (text-to-speech)
- Set, list, and clear time-based **reminders** (with spoken alerts)
- Get the current **weather** for any city
- Read the latest **news headlines**
- Tell the time, date, and the occasional joke

---

## 1. Requirements

- Python 3.8+
- A working microphone and speakers (optional — the app falls back to
  typed input/console output if no mic/audio is available)

## 2. Installation

1. Unzip this project and open a terminal in the project folder.

2. (Recommended) Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   ```

3. Install the Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   **Notes on PyAudio (needed for microphone input):**
   - **Windows:** `pip install pyaudio` usually works directly.
   - **macOS:** Install PortAudio first, then PyAudio:
     ```bash
     brew install portaudio
     pip install pyaudio
     ```
   - **Linux (Debian/Ubuntu):**
     ```bash
     sudo apt-get install python3-pyaudio portaudio19-dev
     pip install pyaudio
     ```

   If PyAudio fails to install, the assistant will still run — it
   automatically falls back to **typed text input** instead of
   microphone input.

   **Notes on pyttsx3 (text-to-speech):**
   - **Linux:** you may need `sudo apt-get install espeak`.
   - **Windows/macOS:** works out of the box using the built-in
     SAPI5 / NSSpeechSynthesizer voices.

## 3. API Keys (for weather & news)

The weather and news features use free third-party APIs. To enable them:

1. Get a free API key from:
   - Weather: https://openweathermap.org/api
   - News: https://newsapi.org/

2. Copy `config_example.py` to `config.py`:

   ```bash
   cp config_example.py config.py
   ```

3. Open `config.py` and paste in your keys:

   ```python
   OPENWEATHER_API_KEY = "your_real_key_here"
   NEWSAPI_KEY = "your_real_key_here"
   ```

   Alternatively, you can set environment variables instead of using
   `config.py`:

   ```bash
   export OPENWEATHER_API_KEY="your_real_key_here"
   export NEWSAPI_KEY="your_real_key_here"
   ```

   If no keys are provided, the assistant will still run — it will
   just tell you those features aren't configured.

## 4. Running the Assistant

```bash
python assistant.py
```

The assistant will greet you and start listening. Speak a command after
you see "Listening... (speak now)". If no microphone is detected, it
will instead prompt you to type your command.

## 5. Example Commands

- "What's the weather in Chennai?"
- "Read the news"
- "What's the news about technology?"
- "Remind me to call mom in 10 minutes"
- "Remind me to take out the trash at 6 pm"
- "List my reminders"
- "Clear my reminders"
- "What time is it?"
- "What's the date today?"
- "Tell me a joke"
- "Help"
- "Exit" / "Quit" / "Goodbye"

## 6. How Reminders Work

Reminders are stored in `reminders.json` in the project folder. A
background thread checks every 5 seconds for due reminders and speaks
them aloud automatically — even while you're not actively giving a
command (as long as the program is still running).

## 7. Extending the Assistant

The code is organized into clear, separate pieces in `assistant.py`:

- `Speaker` — text-to-speech wrapper (pyttsx3)
- `Listener` — speech recognition wrapper (SpeechRecognition + Google
  Speech API), with typed-input fallback
- `ReminderManager` — handles storing/firing reminders
- `get_weather()` / `get_news()` — API integrations
- `Assistant.handle_command()` — the command router; add new `if`
  branches here to support new commands (e.g., calculator, smart-home
  control, calendar lookups, etc.)

Enjoy your assistant!
