# Gemini Computer Use Agent

A minimal browser automation agent using Google's Gemini 2.5 Computer Use Preview model and Playwright for web browser control.

## Features

- **Visual Browser Control**: Uses screenshots to "see" and interact with web pages
- **Automated Actions**: Supports mouse clicks, keyboard input, scrolling, navigation, and more
- **Safety Controls**: Built-in confirmation prompts for risky actions
- **Human-in-the-Loop**: Optional user confirmation for sensitive operations

## Supported Actions

- `open_web_browser`, `navigate`, `search`
- `click_at`, `hover_at`, `type_text_at`
- `key_combination`, `scroll_document`, `scroll_at`
- `drag_and_drop`, `go_back`, `go_forward`
- `wait_5_seconds`

## Setup

### 1. Create and activate environment
```bash
conda create -n gemcu python=3.11 -y
conda activate gemcu
```

### 2. Install packages
```bash
python -m pip install --upgrade pip
python -m pip install google-genai playwright termcolor
```

### 3. Install Playwright browser
```bash
playwright install chromium
```

### 4. Set API key
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"

# Linux/Mac
export GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
```

## Usage

```bash
python agent.py "Find Wikipedia article about Niagara Falls and open History section"
```

## Requirements

- Python 3.11+
- Gemini API key ([Get API key](https://aistudio.google.com/api-keys))
- Chrome/Chromium browser

## Safety

This agent runs in a controlled browser environment. For production use, consider running in a sandboxed virtual machine or container for additional security.

Based on [Google's Gemini Computer Use API](https://ai.google.dev/gemini-api/docs/computer-use).
