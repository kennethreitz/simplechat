import docopt
import re

import xerox
import simplemind as sm
from rich.console import Console
from rich.panel import Panel

from .db import Database
from .settings import get_db_path

AVAILABLE_PROVIDERS = ["xai", "openai", "anthropic", "ollama"]
AVAILABLE_COMMANDS = ["/copy", "/paste", "/help", "/exit", "/clear", "/invoke"]

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

    def __str__(self):
        return f"<Simplechat db_path={self.db_path!r}>"

    def __repr__(self):
        return f"<Simplechat db_path={self.db_path!r}>"

    def set_llm(self, llm_provider, llm_model):
        self.llm_provider = llm_provider
        self.llm_model = llm_model

        self.sm = sm.Session(llm_provider=llm_provider, llm_model=llm_model)

    def set_llm_provider(self, llm_provider):
        if llm_provider not in AVAILABLE_PROVIDERS:
            raise ValueError(f"Unsupported provider: {llm_provider!r}")

        self.llm_provider = llm_provider

    def repl(self):
        """Start an interactive REPL session."""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.styles import Style
        from rich.console import Console
        from prompt_toolkit.completion import WordCompleter

        command_completer = WordCompleter(
            AVAILABLE_COMMANDS, pattern=re.compile(r"/\w*")
        )

        console = Console()
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
                        console.print(
                            "[bold green]Copying to clipboard...[/bold green]"
                        )
                        xerox.copy(user_input)

                    # Paste from clipboard.
                    elif user_input == "/paste":
                        console.print(
                            "[bold green]Pasting from clipboard...[/bold green]"
                        )
                        clipboard_content = xerox.paste()
                        if clipboard_content:
                            # Print the pasted content
                            console.print()  # Add blank line
                            console.print(
                                Panel.fit(
                                    clipboard_content,
                                    title="[bold]Pasted Content[/bold]",
                                    border_style="blue",
                                )
                            )
                    continue

                # Send the input to the LLM and get response
                response = self.sm.send(user_input)
                console.print(f"\n[bold blue]Assistant:[/bold blue] {response}\n")

            except KeyboardInterrupt:
                exit(1)
            except EOFError:
                break
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}\n")

        console.print("\nGoodbye!")


def main():
    args = docopt.docopt(__doc__)

    simplechat = Simplechat()

    # Set the LLM provider and model.
    simplechat.set_llm(llm_provider=args["--provider"], llm_model=args["--model"])

    # Start the conversation.
    simplechat.repl()


if __name__ == "__main__":
    main()
