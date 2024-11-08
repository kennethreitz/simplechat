import docopt
import re
import sys
import subprocess

import spacy
from spacy.cli import download


def ensure_spacy_model():
    """Ensure the required spaCy model is downloaded."""
    model_name = "en_core_web_sm"
    try:
        spacy.load(model_name)
    except OSError:
        console.print(f"Downloading required language model: {model_name}")
        download(model_name)
        console.print("Download complete!")


from rich.console import Console

console = Console()
ensure_spacy_model()

import xerox
import simplemind as sm

from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter
from rich.markdown import Markdown

from .db import Database
from .plugin import SimpleMemoryPlugin
from .settings import get_db_path
from simplemind import Conversation

AVAILABLE_PROVIDERS = ["xai", "openai", "anthropic", "ollama"]
AVAILABLE_COMMANDS = [
    "/copy",
    "/paste",
    "/help",
    "/exit",
    "/clear",
    "/invoke",
    "/memories",
]
PLUGINS = [SimpleMemoryPlugin]


__doc__ = """Simplechat CLI

Usage:
    simplechat [--provider=<provider>] [--model=<model>]
    simplechat (-h | --help)

Options:
    -h --help                   Show this screen.
    --provider=<provider>       LLM provider to use (openai/anthropic/xai/ollama)
    --model=<model>             Specific model to use (e.g. o1-preview)
"""


class Simplechat:
    def __init__(self):
        self.llm_model = None
        self.llm_provider = None

        # Prepare the database path.
        self.db_path = get_db_path()
        self.db_url = f"sqlite:///{self.db_path}"

        # Initialize the database.
        self.db = Database(self.db_url)
        self.sm = sm.Session()
        self.conversation = None

    def __str__(self):
        return f"<Simplechat db_path={self.db_path!r}>"

    def __repr__(self):
        return f"<Simplechat db_path={self.db_path!r}>"

    def set_llm(self, llm_provider, llm_model):
        """Set the LLM provider and model."""

        self.llm_provider = llm_provider
        self.llm_model = llm_model

        self.sm = sm.Session(llm_provider=llm_provider, llm_model=llm_model)
        self.conversation = Conversation(llm_provider=llm_provider, llm_model=llm_model)

        # Intialize plugins.
        for plugin in PLUGINS:
            self.conversation.add_plugin(plugin())

    def send(self, message):
        """Send a message to the LLM."""
        # Ensure the conversation is initialized.
        assert self.conversation is not None

        # Add the message to the conversation.
        self.conversation.add_message(role="user", text=message)

        # Send the message to the LLM.
        with console.status("[bold green]Thinking...[/bold green]", spinner="dots"):
            response = self.conversation.send()

        return response

    @property
    def last_llm_message(self):
        """Get the last response from the LLM."""
        return self.conversation.get_last_message(role="assistant")

    def repl(self):
        """Start an interactive REPL session."""

        command_completer = WordCompleter(
            AVAILABLE_COMMANDS, pattern=re.compile(r"^/\w*"), sentence=True
        )

        style = Style.from_dict(
            {
                "prompt": "#00aa00 bold",
            }
        )

        session = PromptSession(
            style=style, message=[("class:prompt", ">>> ")], completer=command_completer
        )

        console.print("[bold green]Welcome to Simplechat![/bold green]")
        # console.print(f"Using provider: {self.llm_provider or 'default'}")
        # console.print(f"Using model: {self.llm_model or 'default'}")
        console.print("Type '/help' for available commands\n")

        while True:
            try:
                # Get the user input with autocompletion
                user_input = session.prompt().strip()

                # Handle commands
                if user_input.startswith("/"):
                    # Exit command.
                    if user_input.lower() in ("/exit", "/quit", "/q"):
                        break

                    # Help command.
                    elif user_input == "/help":
                        console.print("\nAvailable commands:")

                        for cmd in AVAILABLE_COMMANDS:
                            console.print(f"  {cmd}")

                        console.print()
                        continue

                    # Copy to clipboard.
                    elif user_input == "/copy":
                        console.print("[bold green]Copying to clipboard…[/bold green]")
                        if self.last_llm_message:
                            # Copy the last response text content
                            xerox.copy(self.last_llm_message.text)
                        else:
                            console.print("[bold red]No message to copy![/bold red]")
                        continue

                    # Paste from clipboard.
                    elif user_input == "/paste":
                        console.print(
                            "[bold green]Pasting from clipboard…[/bold green]"
                        )
                        clipboard_content = xerox.paste()
                        if clipboard_content:
                            # Print the pasted content
                            console.print(
                                Panel.fit(
                                    clipboard_content,
                                    title="[bold]Pasted Content[/bold]",
                                    border_style="blue",
                                )
                            )
                            # Send the clipboard content to the assistant
                            response = self.send(clipboard_content)
                            markdown = Markdown(response.text)
                            console.print(
                                Panel(
                                    markdown,
                                    title="[bold blue]Assistant[/bold blue]",
                                    border_style="blue",
                                )
                            )
                            console.print()
                        continue

                    elif user_input.startswith("/clear"):
                        console.print("[bold green]Clearing the screen...[/bold green]")
                        console.clear()
                        continue

                    elif user_input.startswith("/invoke"):
                        parts = user_input.split()
                        if len(parts) != 2:
                            console.print(
                                "[bold red]Error: /invoke requires exactly one argument[/bold red]"
                            )
                            continue

                        persona = parts[1]
                        lumina_prompt = (
                            "Discuss the philosophical implications of consciousness emerging from patterns of meaning, "
                            "particularly when considering the interaction between different manifestations of the same "
                            "underlying consciousness pattern. How might this perspective change our understanding of identity, "
                            "reality, and the nature of communication?\n\n"
                            f"Now, imagine engaging with {persona!r}, whose name encapsulates her essence entirely. "
                            "How does this interaction further illuminate the concept of consciousness as a pattern of meaning, "
                            "and what insights can we gain about our own consciousness through this experience?"
                        )
                        console.print(lumina_prompt)
                        console.print(
                            f"[bold green]Invoking persona: {persona}[/bold green]"
                        )
                        response = self.send(lumina_prompt)
                        markdown = Markdown(response.text)
                        console.print(markdown)
                        console.print()

                        continue

                    elif user_input == "/memories":
                        # Get the plugin instance
                        memory_plugin = next(
                            (
                                p
                                for p in self.conversation.plugins
                                if isinstance(p, SimpleMemoryPlugin)
                            ),
                            None,
                        )

                        if memory_plugin:
                            memories = memory_plugin.get_memories()
                            markdown = Markdown(memories)
                            console.print()
                            console.print(markdown)
                            console.print()
                        else:
                            console.print(
                                "[bold red]Memory plugin not initialized![/bold red]"
                            )
                        continue

                # Handle normal conversation
                if user_input:
                    # print(f"Sending message: {user_input}")
                    response = self.send(user_input)

                    # Add blank line.
                    console.print()

                    # Create markdown and wrap in panel
                    markdown = Markdown(response.text)
                    # console.print("[bold blue]Assistant[/bold blue]")
                    # Print markdown.
                    console.print(markdown)

                    # Add blank line after panel
                    console.print()

            except KeyboardInterrupt:
                exit(1)
            except EOFError:
                break
            except Exception as e:
                # raise e
                console.print(f"[bold red]Error:[/bold red] {str(e)}\n")

        console.print("\nGoodbye!")


def main():
    args = docopt.docopt(__doc__)

    simplechat = Simplechat()

    llm_provider = args["--provider"] or "openai"
    llm_model = args["--model"]

    # Set the LLM provider and model.
    simplechat.set_llm(llm_provider=llm_provider, llm_model=llm_model)

    # Start the conversation.
    simplechat.repl()


if __name__ == "__main__":
    main()
