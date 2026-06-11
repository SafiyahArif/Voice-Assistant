"""
Voice-Activated Personal Assistant
-----------------------------------
Features:
  - Wake-word free, push-to-listen voice commands
  - Set / list / cancel reminders (with background notification thread)
  - Get current weather for a city (OpenWeatherMap API)
  - Read top news headlines (NewsAPI)
  - Text-to-speech responses
  - Fallback to typed text input if microphone isn't available

Run:
    python assistant.py

Configuration:
    Copy config_example.py to config.py and add your API keys,
    OR set the OPENWEATHER_API_KEY and NEWSAPI_KEY environment variables.
"""

import os
import re
import sys
import time
import json
import queue
import threading
import datetime as dt

import speech_recognition as sr
import pyttsx3
import requests

try:
    import config
    OPENWEATHER_API_KEY = getattr(config, "OPENWEATHER_API_KEY", "")
    NEWSAPI_KEY = getattr(config, "NEWSAPI_KEY", "")
except ImportError:
    OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
    NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")

REMINDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")


# --------------------------------------------------------------------------- #
# Text-to-Speech
# --------------------------------------------------------------------------- #
class Speaker:
    """Wraps pyttsx3 so it can be safely called from multiple threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", 175)

    def say(self, text):
        print(f"Assistant: {text}")
        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()


# --------------------------------------------------------------------------- #
# Speech Recognition
# --------------------------------------------------------------------------- #
class Listener:
    """Wraps SpeechRecognition microphone input with a typed-input fallback."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.mic_available = True
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except (OSError, AttributeError):
            self.mic_available = False
            self.microphone = None

    def listen(self):
        """Return recognized text (lowercase) or '' on failure/timeout."""
        if not self.mic_available:
            try:
                return input("You (type your command): ").strip().lower()
            except EOFError:
                return ""

        with self.microphone as source:
            print("Listening... (speak now)")
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
            except sr.WaitTimeoutError:
                return ""

        try:
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text.lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"Speech recognition service error: {e}")
            return ""


# --------------------------------------------------------------------------- #
# Reminders
# --------------------------------------------------------------------------- #
class ReminderManager:
    """Stores reminders on disk and fires them via a background thread."""

    def __init__(self, speaker: Speaker):
        self.speaker = speaker
        self.lock = threading.Lock()
        self.reminders = self._load()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def _load(self):
        if os.path.exists(REMINDERS_FILE):
            try:
                with open(REMINDERS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save(self):
        with open(REMINDERS_FILE, "w") as f:
            json.dump(self.reminders, f, indent=2)

    def add(self, text, when: dt.datetime):
        with self.lock:
            self.reminders.append({
                "text": text,
                "time": when.isoformat(),
                "fired": False,
            })
            self._save()

    def list_active(self):
        with self.lock:
            return [r for r in self.reminders if not r["fired"]]

    def clear_all(self):
        with self.lock:
            self.reminders = []
            self._save()

    def _watch_loop(self):
        while not self._stop_event.is_set():
            now = dt.datetime.now()
            with self.lock:
                changed = False
                for r in self.reminders:
                    if r["fired"]:
                        continue
                    when = dt.datetime.fromisoformat(r["time"])
                    if now >= when:
                        r["fired"] = True
                        changed = True
                        text = r["text"]
                        threading.Thread(
                            target=self.speaker.say,
                            args=(f"Reminder: {text}",),
                            daemon=True,
                        ).start()
                if changed:
                    self._save()
            time.sleep(5)

    def stop(self):
        self._stop_event.set()


# --------------------------------------------------------------------------- #
# Weather
# --------------------------------------------------------------------------- #
def get_weather(city: str) -> str:
    if not OPENWEATHER_API_KEY:
        return ("I can't fetch the weather because no OpenWeatherMap API key "
                "is configured. Add OPENWEATHER_API_KEY to config.py or your "
                "environment variables.")

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if resp.status_code != 200:
            return f"Sorry, I couldn't get the weather for {city}. {data.get('message', '')}"

        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        return (f"The weather in {city} is currently {desc}, with a temperature of "
                f"{temp:.1f} degrees Celsius, feeling like {feels:.1f} degrees, "
                f"and humidity at {humidity} percent.")
    except requests.RequestException as e:
        return f"I had trouble reaching the weather service: {e}"


# --------------------------------------------------------------------------- #
# News
# --------------------------------------------------------------------------- #
def get_news(topic: str = None, count: int = 5) -> str:
    if not NEWSAPI_KEY:
        return ("I can't fetch news because no NewsAPI key is configured. "
                "Add NEWSAPI_KEY to config.py or your environment variables.")

    url = "https://newsapi.org/v2/top-headlines"
    params = {"apiKey": NEWSAPI_KEY, "pageSize": count, "language": "en"}
    if topic:
        params["q"] = topic
        url = "https://newsapi.org/v2/everything"
        params["sortBy"] = "publishedAt"
    else:
        params["country"] = "us"

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if resp.status_code != 200 or data.get("status") != "ok":
            return f"Sorry, I couldn't fetch the news. {data.get('message', '')}"

        articles = data.get("articles", [])
        if not articles:
            return "I couldn't find any news articles right now."

        headlines = [a["title"] for a in articles[:count]]
        return "Here are the top headlines: " + ". Next: ".join(headlines)
    except requests.RequestException as e:
        return f"I had trouble reaching the news service: {e}"


# --------------------------------------------------------------------------- #
# Command parsing helpers
# --------------------------------------------------------------------------- #
TIME_PATTERN = re.compile(
    r"(?:in\s+(?P<num>\d+)\s+(?P<unit>second|minute|hour)s?)"
    r"|(?:at\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?)"
)


def parse_reminder_time(command: str):
    """Parse a relative ('in 10 minutes') or absolute ('at 5 pm') time."""
    match = TIME_PATTERN.search(command)
    now = dt.datetime.now()

    if not match:
        return None

    if match.group("num"):
        num = int(match.group("num"))
        unit = match.group("unit")
        delta_kwargs = {f"{unit}s": num}
        return now + dt.timedelta(**delta_kwargs)

    if match.group("hour"):
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        ampm = match.group("ampm")
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += dt.timedelta(days=1)
        return target

    return None


def extract_reminder_text(command: str) -> str:
    """Strip 'remind me to ... in/at ...' down to just the task text."""
    text = re.sub(r"^(remind me to|set a reminder to|set reminder to|remind me)\s*", "", command)
    text = TIME_PATTERN.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text or "your reminder"


def extract_city(command: str) -> str:
    match = re.search(r"weather (?:in|for|at)\s+(.+)", command)
    if match:
        return match.group(1).strip().rstrip("?.!")
    return "your city"


# --------------------------------------------------------------------------- #
# Main assistant loop
# --------------------------------------------------------------------------- #
HELP_TEXT = (
    "You can ask me things like: "
    "'what's the weather in London', "
    "'remind me to call mom in 10 minutes', "
    "'remind me to take out the trash at 6 pm', "
    "'list my reminders', "
    "'read the news', "
    "'tell me a joke', or say 'exit' to quit."
)

JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "I told my computer I needed a break, and it said no problem, it'll go to sleep.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I would tell you a joke about UDP, but you might not get it.",
]


class Assistant:
    def __init__(self):
        self.speaker = Speaker()
        self.listener = Listener()
        self.reminders = ReminderManager(self.speaker)

    def respond(self, text):
        self.speaker.say(text)

    def handle_command(self, command: str) -> bool:
        """Process one command. Return False to exit the assistant."""
        if not command:
            return True

        if any(word in command for word in ["exit", "quit", "stop", "goodbye", "bye"]):
            self.respond("Goodbye! Have a great day.")
            return False

        if "help" in command or "what can you do" in command:
            self.respond(HELP_TEXT)
            return True

        if "weather" in command:
            city = extract_city(command)
            if city == "your city":
                self.respond("Which city's weather would you like?")
                follow_up = self.listener.listen()
                city = follow_up.strip() or "London"
            self.respond(get_weather(city))
            return True

        if "news" in command or "headline" in command:
            topic = None
            match = re.search(r"news (?:about|on)\s+(.+)", command)
            if match:
                topic = match.group(1).strip().rstrip("?.!")
            self.respond(get_news(topic))
            return True

        if "remind" in command:
            when = parse_reminder_time(command)
            text = extract_reminder_text(command)
            if when is None:
                self.respond(
                    "I didn't catch a time. Try saying something like "
                    "'remind me to drink water in 20 minutes' or 'at 6 pm'."
                )
                return True
            self.reminders.add(text, when)
            self.respond(
                f"Okay, I'll remind you to {text} at "
                f"{when.strftime('%I:%M %p on %B %d')}."
            )
            return True

        if "list" in command and "reminder" in command:
            active = self.reminders.list_active()
            if not active:
                self.respond("You have no active reminders.")
            else:
                parts = []
                for r in active:
                    when = dt.datetime.fromisoformat(r["time"])
                    parts.append(f"{r['text']} at {when.strftime('%I:%M %p')}")
                self.respond("Your reminders are: " + "; ".join(parts))
            return True

        if "clear" in command and "reminder" in command:
            self.reminders.clear_all()
            self.respond("All reminders have been cleared.")
            return True

        if "time" in command and "what" in command:
            now = dt.datetime.now().strftime("%I:%M %p")
            self.respond(f"It's currently {now}.")
            return True

        if "date" in command and "what" in command:
            today = dt.datetime.now().strftime("%A, %B %d, %Y")
            self.respond(f"Today is {today}.")
            return True

        if "joke" in command:
            import random
            self.respond(random.choice(JOKES))
            return True

        self.respond(
            "Sorry, I didn't understand that. Say 'help' to hear what I can do."
        )
        return True

    def run(self):
        self.respond(
            "Hello! I'm your personal assistant. " + HELP_TEXT
        )
        running = True
        while running:
            command = self.listener.listen()
            if command:
                running = self.handle_command(command)


def main():
    assistant = Assistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye!")
    finally:
        assistant.reminders.stop()


if __name__ == "__main__":
    main()
