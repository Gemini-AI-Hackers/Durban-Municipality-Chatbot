
# WhatsApp Chatbot with ngrok

This project demonstrates how to run a simple WhatsApp chatbot using Python, Flask, and ngrok. The chatbot is hosted locally and exposed to the internet using ngrok, allowing it to interact with users on WhatsApp.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Chatbot](#running-the-chatbot)
- [Using the Chatbot](#using-the-chatbot)
- [Stopping the Chatbot](#stopping-the-chatbot)
- [Contributing](#contributing)
- [License](#license)

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- Python 3.x: [Download Python](https://www.python.org/downloads/)
- Pip (Python package manager): Included with Python 3.x
- Ngrok: [Download ngrok](https://ngrok.com/download)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Gemini-AI-Hackers/Durban-Municipality-Chatbot
```

### 2. Install Python Dependencies

Use pip to install the required Python packages:

```bash
pip install -r requirements.txt
```

Alternatively, manually install the necessary packages:

```bash
pip install flask 
```

## Configuration

### 1. Configure Your Flask App

Open the `bot.py` file and ensure your Flask app is configured properly.

## Running the Chatbot

### 1. Start the Flask Application

Run the Flask server locally:

```bash
python bot.py
```

### 2. Expose the Local Server Using ngrok

In a new terminal window, run ngrok:

```bash
ngrok http 5000
```

- Copy the `https://<ngrok-id>.ngrok.io` URL provided by ngrok.
- Add the URL to Facebook Meta Developers Page

## Using the Chatbot

- Send a message to your WhatsApp number.
- The chatbot will respond based on the logic defined in `bot.py`.

### Example Interactions

- Send "hello" to receive a greeting and a pathway on what you might need assistance on.


## Stopping the Chatbot

To stop the chatbot:

- Stop ngrok by closing the terminal or pressing `Ctrl + C`.

