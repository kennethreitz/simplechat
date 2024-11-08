# Simplechat

A chat interface for AI models using Simplemind.

## Overview

Simplechat is a command-line chat application that provides an interactive interface for conversing with AI models. It features memory persistence, context awareness, and support for multiple AI providers.

## Features

- Support for multiple AI providers (OpenAI, Anthropic, XAI, Ollama)
- Persistent conversation memory and context
- Entity and topic tracking
- User identity management
- Rich markdown rendering
- Command completion
- Clipboard integration

## Installation

Requires Python 3.11 or higher.

```bash
$ pip install simplemind-chat
```

## Usage

Start a chat session:

```bash
$ simplechat [--provider=<provider>] [--model=<model>]
```

API keys should be set in environment variables before running:

```bash
$ export OPENAI_API_KEY="..."
$ export ANTHROPIC_API_KEY="..."
$ export XAI_API_KEY="..."
$ export OLLAMA_API_KEY="..."
```

Options:
- `--provider`: LLM provider to use (openai/anthropic/xai/ollama)
- `--model`: Specific model to use (e.g. o1-preview)

### Available Commands

- `/copy` - Copy last assistant response to clipboard
- `/paste` - Paste clipboard content into chat
- `/help` - Show available commands
- `/exit` - Exit the chat session
- `/clear` - Clear the screen
- `/invoke` - Invoke a specific persona
- `/memories` - Display conversation memories

## Features in Detail

### Memory System
Simplechat includes a sophisticated memory system that:
- Tracks conversation topics and entities
- Maintains user identity across sessions
- Records user preferences and characteristics
- Provides context awareness for more coherent conversations

### Database
Uses SQLite for persistent storage of:
- Conversation entities
- User identity
- Essence markers (user characteristics and preferences)
- Memory markers

### Rich Interface
- Markdown rendering for formatted output
- Command completion
- Status indicators
- Error handling with retries

## Development

The project structure follows a modular design:
- `cli.py`: Command-line interface and main chat loop
- `db.py`: Database operations and schema
- `plugin.py`: Plugin system for memory and context management
- `settings.py`: Configuration and path management

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
