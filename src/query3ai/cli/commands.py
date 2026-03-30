import os
import json
import re
from pathlib import Path
import typer  # type: ignore
from rich.console import Console, Group  # type: ignore
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn  # type: ignore
from rich.panel import Panel  # type: ignore
from rich.table import Table  # type: ignore
from rich.tree import Tree  # type: ignore
from rich.prompt import Confirm, Prompt  # type: ignore
from rich.text import Text  # type: ignore
from rich.rule import Rule  # type: ignore
from rich.json import JSON  # type: ignore
from rich.markdown import Markdown  # type: ignore
import readchar  # type: ignore

from query3ai.services.document_service import extract_text, chunk_text  # type: ignore
from query3ai.services.reasoning_service import answer  # type: ignore
from query3ai.services.tree_service import build_tree  # type: ignore
from query3ai.services.decision_service import filter_nodes  # type: ignore
from query3ai.services.graph_service import store_tree, get_nodes, get_all_nodes, delete_document  # type: ignore
from query3ai.db.neo4j_client import neo4j_client  # type: ignore
from query3ai.config.settings import settings, DEFAULT_TREE_PROMPT, DEFAULT_DECISION_PROMPT, DEFAULT_REASONING_PROMPT  # type: ignore
from query3ai.config.paths import TEMP_OUTPUT_DIR  # type: ignore

from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import Window, HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from query3ai.config.paths import (
    WORKSPACE_DIR,
    COMPOSE_PATH,
    CONFIG_PATH,
    ensure_workspace,
)

import subprocess
from query3ai.config.paths import COMPOSE_PATH


app = typer.Typer(help="Query3AI - Intelligent document query system")
console = Console()


def handle_error(e: Exception):
    err_str = str(e).lower()

    # 1. Ollama-specific errors
    if "connection refused" in err_str and "11434" in err_str:
        console.print(
            "[bold red]API Error:[/bold red] Ollama connection failed. [yellow]Start Ollama with: ollama serve[/yellow]"
        )
    # 2. Model missing errors
    elif "not found" in err_str and "model" in err_str:
        console.print(
            f"[bold red]Model Error:[/bold red] Model not pulled. [yellow]Run: ollama pull <model_name>[/yellow]\n[dim]Details: {e}[/dim]"
        )
    # 3. AI Model connection errors (Generic)
    elif (
        "ai model connection error" in err_str
        or "api key" in err_str
        or "unauthorized" in err_str
    ):
        console.print(
            "[bold red]AI Model Error:[/bold red] Could not connect to the AI Provider.\n"
            "[yellow]Check your API keys, network connection, or if the service is running.[/yellow]\n"
            f"[dim]Details: {e}[/dim]"
        )
    # 4. Neo4j/DB Errors (Be more specific than just 'connection')
    elif (
        "serviceunavailable" in err_str
        or "neo4j" in err_str
        or "bolt" in err_str
        or "driver" in err_str
    ):
        console.print(
            f"[bold red]DB Error:[/bold red] Neo4j connection failed. Please verify URI and credentials.\n[dim]Details: {e}[/dim]"
        )
    # 5. Catch-all for other connection issues not yet classified
    elif "connection" in err_str:
        console.print(
            f"[bold red]Network Error:[/bold red] A connection problem occurred.\n[dim]Details: {e}[/dim]"
        )
    else:
        from rich.text import Text

        error_text = Text(str(e))
        console.print(Panel(error_text, title="Error", border_style="red"))


def confirm_with_border(question_str: str) -> bool:

    plain_title = Text.from_markup(question_str).plain.strip()
    text_area = TextArea(prompt=" [y/n] > ", multiline=False)

    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event):
        ans = text_area.text.strip().lower()
        if ans in ("y", "yes", ""):
            event.app.exit(result=True)
        elif ans in ("n", "no"):
            event.app.exit(result=False)
        else:
            text_area.text = ""

    @bindings.add("c-c", "c-d")
    def _(event):
        event.app.exit(result=False)

    header = Window(
        content=FormattedTextControl(text=f"  {plain_title}"),
        height=len(plain_title.split("\n")),
        style="class:frame.label",
    )

    input_frame = Frame(body=HSplit([header, text_area]), style="class:frame")

    app = Application(
        layout=Layout(input_frame),
        key_bindings=bindings,
        style=Style.from_dict(
            {
                "frame": "fg:#4499ff",
                "frame.label": "fg:#888888",
            }
        ),
        full_screen=False,
    )
    return app.run()


@app.command("ingest")
def ingest(
    file_path: str,
):
    """
    Ingest a document, extract text, chunk it, build tree, and store in Neo4j.
    """

    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        console.print(
            Panel(f"File not found: {file_path}", title="Error", border_style="red")
        )
        return

    doc_id = os.path.basename(file_path)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True,
        ) as progress:
            total_steps = 3
            task = progress.add_task(
                description=f"Extracting text from {file_path}...", total=total_steps
            )

            # 1. Extract & Chunk
            text = extract_text(file_path)
            chunks = chunk_text(text, chunk_size=settings.CHUNK_SIZE)
            progress.update(task, advance=1)

            # 2. Build Tree via Tree Agent
            progress.update(
                task,
                description=f"Building tree structure with {settings.get_active_tree_model()}...",
            )
            tree_data = build_tree(chunks)
            if not tree_data.get("title"):
                tree_data["title"] = doc_id
            progress.update(task, advance=1)

            # 3. Store in Neo4j
            progress.update(task, description="Storing to Neo4j...")
            store_tree(tree_data, doc_id, chunks)
            progress.update(task, advance=1, description="Done!")

        console.print(
            f"[bold green]Success![/bold green] Ingested document '{doc_id}' into Neo4j graph with {len(chunks)} chunks."
        )
    except Exception as e:
        handle_error(e)


@app.command("list")
def list_docs():
    """
    List all documents currently stored in Neo4j.
    """
    try:
        nodes = neo4j_client.get_nodes("Document")

        if not nodes:
            console.print("[yellow]No documents found in the database.[/yellow]")
            return

        table = Table(title="Ingested Documents")
        table.add_column("ID", style="cyan")
        table.add_column("Filename", style="magenta")
        table.add_column("Chunks", justify="right")
        table.add_column("Sections", justify="right")
        table.add_column("Ingested At", style="dim")

        for idx, node in enumerate(nodes):
            table.add_row(
                node.get("doc_id", "Unknown"),
                node.get("filename", node.get("doc_id", "Unknown")),
                str(node.get("chunk_count", "-")),
                str(node.get("section_count", "-")),
                node.get("ingested_at", "-"),
            )

        console.print(table)
    except Exception as e:
        handle_error(e)


@app.command("inspect")
def inspect(doc_id: str):
    """
    Inspect the tree structure of an ingested document.
    """
    try:
        data = get_nodes(doc_id)
        if not data:
            console.print(f"[yellow]Document '{doc_id}' not found.[/yellow]")
            return

        doc_info = data.get("document", {})
        chapters = data.get("chapters", [])

        tree = Tree(
            f"[bold magenta]📄 {doc_info.get('title', 'Unknown Title')}[/bold magenta] (ID: {doc_info.get('doc_id')})"
        )

        for chap in chapters:
            chap_branch = tree.add(
                f"[bold blue]📑 {chap.get('heading', 'Chapter')}[/bold blue]"
            )
            if chap.get("summary"):
                chap_branch.add(f"[dim]Summary: {chap['summary']}[/dim]")
            
            for sec in chap.get("sections", []):
                sec_branch = chap_branch.add(
                    f"[bold cyan]📁 {sec.get('heading', 'Section')}[/bold cyan]"
                )
                if sec.get("summary"):
                    sec_branch.add(f"[dim]Summary: {sec['summary']}[/dim]")

                chunks_branch = sec_branch.add("[green]🧩 Chunks[/green]")
                for chunk in sec.get("chunks", []):
                    text_val = str(chunk.get("text", ""))
                    chunk_text_preview = text_val[:50].replace("\n", " ") + "..."  # type: ignore
                    chunks_branch.add(
                        f"[yellow]Idx {chunk.get('index')}[/yellow]: {chunk_text_preview}"
                    )

        console.print(tree)
    except Exception as e:
        handle_error(e)


def interactive_document_menu(
    documents: list, question: str, current_selection: str = "0"
) -> str | None:
    """Show the interactive document selection menu using readchar and up/down arrows."""
    options = [("0", "Search All Documents Globally")]
    for idx, doc in enumerate(documents, start=1):
        doc_id = doc.get("doc_id", f"Doc_{idx}")
        title = doc.get("title", doc_id)
        options.append((str(idx), f"{title} ({doc_id})"))

    # Try to find the previous selection to default to it
    selected = 0
    for i, (val, _) in enumerate(options):
        if val == current_selection:
            selected = i
            break

    while True:
        console.clear()

        try:
            size = os.get_terminal_size()
            term_width = int(size.columns)
            term_height = int(size.lines)
        except Exception:
            term_width = 80
            term_height = 24

        used_lines = 0
        header = Group(
            Rule(style="dim"),
            Text("Select Target Document Context:", style="bold cyan"),
        )
        console.print(header)
        used_lines += 2

        lines = []
        for i, (val, desc) in enumerate(options):
            inner_len = int(term_width) - 8
            if inner_len < 20:
                inner_len = 20

            if i == selected:
                lines.append(
                    Text(
                        f" > [{val}] {desc} ".ljust(inner_len),
                        style="bold green on #1e3524",
                    )
                )
            else:
                lines.append(
                    Text(f"   [{val}] {desc} ".ljust(inner_len), style="dim white")
                )

        body = []
        for i, line in enumerate(lines):
            body.append(line)
            if i < len(lines) - 1:
                body.append(Text(""))

        options_panel = Panel(
            Group(*body),
            border_style="cyan",
            padding=(0, 1),
            expand=True,
        )
        console.print(options_panel)
        used_lines += (len(lines) * 2 - 1) + 2  # Panels and rules eat space

        instruction = Text(
            "  ↑↓ to navigate  · Enter to select  · Esc to cancel", style="dim"
        )
        used_lines += 2

        pad_lines = int(term_height) - int(used_lines) - 8
        if pad_lines > 0:
            console.print("\n" * pad_lines)

        console.print(instruction)

        input_panel = Panel(
            f"[bold blue]Active Query:[/bold blue] {question}",
            border_style="blue",
            padding=(0, 1),
            expand=True,
        )
        console.print(input_panel)

        key = readchar.readkey()
        if key == readchar.key.UP:
            selected = (int(selected) - 1) % len(options)
        elif key == readchar.key.DOWN:
            selected = (int(selected) + 1) % len(options)
        elif key in (readchar.key.ENTER, "\r", "\n"):
            return options[int(selected)][0]
        elif key == readchar.key.ESC:
            return None


@app.command("ask")
def ask(
    question: str,
):
    """
    Ask a question based on ingested documents.
    """

    try:

        documents = neo4j_client.get_nodes("Document")
        if not documents:
            console.print(
                "[yellow]No documents ingested yet. Please run 'ingest' first.[/yellow]"
            )
            return

        console.print("\n[bold cyan]Loading Document Context Menu...[/bold cyan]")
        doc_map = {}
        for idx, doc in enumerate(documents, start=1):
            doc_id = doc.get("doc_id", f"Doc_{idx}")
            doc_map[str(idx)] = doc_id

        selection = interactive_document_menu(documents, question)

        if selection is None:
            console.print("[dim]Selection cancelled. Exiting query.[/dim]")
            return

        if selection == "0":
            target_nodes = get_all_nodes()
        elif selection in doc_map:
            doc_data = get_nodes(doc_map[selection])
            target_nodes = [sec for chap in doc_data.get("chapters", []) for sec in chap.get("sections", [])] if doc_data else []
        else:
            console.print("[red]Invalid selection. Exiting object graph.[/red]")
            return

        if not target_nodes:
            console.print("[yellow]No valid sections found in selection.[/yellow]")
            return

        console.print(
            f"[dim cyan]🔌 Decision Model: {settings.get_active_decision_model()}[/dim cyan]"
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                description=f"Decision Agent: Searching context with {settings.get_active_decision_model()}...",
                total=None,
            )

            # Decision Agent: Filter relevant ones
            filtered_nodes = filter_nodes(question, target_nodes)

        if filtered_nodes:
            import json

            preview_data = [
                {
                    "node_id": n.get("node_id"),
                    "heading": n.get("heading"),
                    "summary": n.get("summary"),
                    "document_name": n.get(
                        "doc_title", n.get("document_name", "Unknown")
                    ),
                    "document_id": n.get("doc_id", "Unknown"),
                }
                for n in filtered_nodes
            ]
            console.print("\n[cyan]Decision Agent Extracted Context:[/cyan]")
            json_str = json.dumps(preview_data, indent=2)
            console.print(Panel(JSON(json_str), border_style="yellow", expand=True))

            proceed = confirm_with_border(
                "\n[bold yellow]Do you want to pass this exact compiled context to the Reasoning Model?[/bold yellow]"
            )
            if not proceed:
                console.print("[dim]Query canceled cleanly.[/dim]\n")
                return

        console.print(
            f"\n[dim cyan]🔌 Reasoning Model: {settings.get_active_reasoning_model()}[/dim cyan]"
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                description=f"Reasoning Agent: Thinking with {settings.get_active_reasoning_model()}...",
                total=None,
            )

            # Reasoning Agent: Generate final answer
            response_text = answer(question, context_nodes=filtered_nodes)

        console.print("\nAnswer:")
        console.print(Panel(response_text, border_style="green"))

        console.print("\nSources:")
        if not filtered_nodes:
            console.print("- [dim]None[/dim]")
        for node in filtered_nodes:
            heading = node.get("heading", "Untitled Section")
            console.print(f"- [cyan]Section:[/cyan] {heading}")

    except Exception as e:
        handle_error(e)


@app.command("delete")
def delete(doc_id: str):
    """
    Removes Document node and all child Section + Chunk nodes from Neo4j.
    """
    should_delete = confirm_with_border(
        f"Are you sure you want to delete document '{doc_id}'?"
    )
    if should_delete:
        try:
            delete_document(doc_id)
            console.print(
                f"[bold green]Successfully deleted '{doc_id}' from the database.[/bold green]"
            )
        except Exception as e:
            handle_error(e)
    else:
        console.print("[yellow]Deletion cancelled.[/yellow]")


@app.command("chat")
def chat():
    """
    Start an interactive chat session based on ingested documents.
    """

    try:
        all_section_nodes = get_all_nodes()
        if not all_section_nodes:
            console.print(
                "[yellow]Note: No documents ingested yet. You can use /ingest within the chat to add them.[/yellow]"
            )
            all_section_nodes = []

        def draw_splash():
            os.system("cls" if os.name == "nt" else "clear")
            try:
                term_height = int(os.get_terminal_size().lines)
            except Exception:
                term_height = 24

            logo = """
  ___                       _____    _    ___ 
 / _ \\ _   _  ___ _ __ _   |__  /   / \\  |_ _|
| | | | | | |/ _ \\ '__| | | |/ /   / _ \\  | | 
| |_| | |_| |  __/ |  | |_| / /_  / ___ \\ | | 
 \\__\\_\\\\__,_|\\___|_|   \\__,/____|/_/   \\_\\___|"""

            console.print("\n")
            console.print(Text(logo, style="bold #1c39bb", justify="left"))
            console.print("\n")
            console.print(
                Text("Welcome to Query3AI Interactive Chat!", style="bold green")
            )
            console.print(
                Text("Type '/help' to see all available commands.", style="dim")
            )
            console.print(
                f"\n[dim cyan]🔌 Active Models:\n  Tree:      {settings.get_active_tree_model()}\n  Decision:  {settings.get_active_decision_model()}\n  Reasoning: {settings.get_active_reasoning_model()}[/dim cyan]"
            )

            pad_lines = term_height - 18
            if pad_lines > 0:
                console.print("\n" * pad_lines, end="")

        draw_splash()

        from prompt_toolkit import prompt  # type: ignore
        from prompt_toolkit.keys import Keys  # type: ignore
        from prompt_toolkit.key_binding import KeyBindings  # type: ignore
        from prompt_toolkit.styles import Style  # type: ignore
        from prompt_toolkit.formatted_text import HTML  # type: ignore

        SLASH_COMMANDS = [
            ("/about", "Learn about Query3AI Interactive Chat."),
            ("/help", "Display usage and commands."),
            ("/version", "Show currently installed version from pyproject.toml."),
            ("/ingest", "Ingest a new document from a specified file path."),
            ("/listdocs", "List indexed documentation."),
            ("/list", "List available assets."),
            ("/listpreresource", "List the number of temporary JSON files created."),
            ("/deletedoc", "Remove a specific document from the database."),
            ("/cleanupdocs", "Delete all documents from the database."),
            ("/cleanupresorce", "Clean up temporary logs and JSON files."),
            ("/clear", "Clear chat history."),
            ("/exit", "Exit the interactive session."),
        ]

        def interactive_slash_menu() -> str | None:
            """Show the slash command menu and return selected command or None."""
            query = "/"
            selected = 0

            while True:
                # Clear and redraw
                console.clear()

                try:
                    term_width = int(os.get_terminal_size().columns)
                    term_height = int(os.get_terminal_size().lines)
                except Exception:
                    term_width = 80
                    term_height = 24

                used_lines = 0

                header = Group(
                    Text("Welcome to Query3AI Interactive Chat!", style="bold green"),
                    Text(
                        "Type '/help' to see all available console commands.\n",
                        style="dim",
                    ),
                )
                console.print(header)
                used_lines += 3

                # Filter commands
                filtered = [c for c in SLASH_COMMANDS if c[0].startswith(query.lower())]

                options_renderable = None

                if filtered:
                    selected = max(0, min(selected, len(filtered) - 1))
                    lines = []
                    for i, (cmd, desc) in enumerate(filtered):
                        inner_len = int(term_width) - 8
                        if inner_len < 20:
                            inner_len = 20
                        entry = f"{cmd:<12}  {desc}"
                        padded = entry.ljust(inner_len)

                        if i == selected:
                            line_text = Text(
                                f"  {padded}  ", style="bold green on #1e3524"
                            )
                        else:
                            line_text = Text()
                            line_text.append(f"  {cmd:<12}  ", style="bold white")
                            line_text.append(
                                f"{desc.ljust(inner_len - 14)}  ", style="dim white"
                            )
                        lines.append(line_text)

                    body = []
                    for i, line in enumerate(lines):
                        body.append(line)
                        if i < len(lines) - 1:
                            body.append(Text(""))

                    options_renderable = Group(
                        Rule(style="dim"),
                        Panel(
                            Group(*body),
                            border_style="green",
                            padding=(0, 1),
                            expand=True,
                        ),
                    )
                    used_lines += len(lines) * 2 + 1 + 2
                else:
                    options_renderable = Group(
                        Rule(style="dim"),
                        Text(
                            f"No commands match '{query}' — will be sent as regular message.",
                            style="dim",
                        ),
                    )
                    used_lines += 2

                if options_renderable:
                    console.print(options_renderable)

                instruction = Text(
                    "  ↑↓ to navigate  · Enter to select  · Esc to cancel  · Type to search",
                    style="dim",
                )
                used_lines += 2

                pad_lines = term_height - used_lines - 4
                if pad_lines > 0:
                    console.print("\n" * pad_lines)

                console.print(instruction)

                input_panel = Panel(
                    f"[dim](press / for slash commands)[/dim]\n> {query}[blink]_[/blink]",
                    border_style="blue",
                    padding=(0, 1),
                    expand=True,
                )
                console.print(input_panel)

                key = readchar.readkey()
                if key == readchar.key.UP:
                    if filtered:
                        selected = (selected - 1) % len(filtered)
                elif key == readchar.key.DOWN:
                    if filtered:
                        selected = (selected + 1) % len(filtered)
                elif key in (readchar.key.ENTER, "\r", "\n"):
                    if filtered:
                        return filtered[selected][0]
                    else:
                        return query
                elif key == readchar.key.ESC:
                    return None
                elif key in (readchar.key.BACKSPACE, "\x08", "\x7f"):
                    query = query[:-1]
                    if not query:
                        return None
                    selected = 0
                else:
                    if isinstance(key, str) and len(key) == 1 and key.isprintable():
                        query += key
                        selected = 0

        def interactive_delete_menu(doc_options: list) -> str | None:
            """Show the interactive document selection menu for deletion."""
            query = ""
            selected = 0
            while True:
                console.clear()
                console.print("[bold red]Delete Document Selection[/bold red]")
                console.print("[dim]Type to filter documents by ID/Title...[/dim]\n")

                try:
                    size = os.get_terminal_size()
                    term_width = int(size.columns)
                    term_height = int(size.lines)
                except Exception:
                    term_width = 80
                    term_height = 24

                used_lines = 3  # Header

                filtered = [
                    (d_id, d_title)
                    for d_id, d_title in doc_options
                    if query.lower() in d_id.lower() or query.lower() in d_title.lower()
                ]

                options_renderable = None

                if filtered:
                    selected = max(0, min(selected, len(filtered) - 1))
                    lines = []
                    for i, (d_id, d_title) in enumerate(filtered):
                        inner_len = int(term_width) - 8
                        if inner_len < 20:
                            inner_len = 20

                        entry = f"ID: {d_id}  |  Title: {d_title}"
                        if len(entry) > inner_len:
                            entry = entry[: inner_len - 3] + "..."  # type: ignore
                        padded = entry.ljust(inner_len)

                        if i == selected:
                            lines.append(
                                Text(
                                    f" > {padded}  ",
                                    style="bold white on #8b0000",
                                )
                            )
                        else:
                            lines.append(Text(f"   {padded}  ", style="dim white"))

                    body = []
                    for i, line in enumerate(lines):
                        body.append(line)
                        if i < len(lines) - 1:
                            body.append(Text(""))

                    options_renderable = Group(
                        Rule(style="dim red"),
                        Panel(
                            Group(*body),
                            border_style="red",
                            padding=(0, 1),
                            expand=True,
                        ),
                    )
                    used_lines += len(lines) * 2 + 1 + 2
                else:
                    options_renderable = Group(
                        Rule(style="dim red"),
                        Text(
                            f"No documents match '{query}' — will use exact string.",
                            style="dim",
                        ),
                    )
                    used_lines += 2

                if options_renderable:
                    console.print(options_renderable)

                instruction = Text(
                    "  ↑↓ to navigate  · Enter to select  · Esc to cancel  · Type to search",
                    style="dim",
                )
                used_lines += 2

                pad_lines = term_height - used_lines - 4
                if pad_lines > 0:
                    console.print("\n" * int(pad_lines))

                console.print(instruction)

                input_panel = Panel(
                    f"> {query}[blink]_[/blink]",
                    border_style="red",
                    padding=(0, 1),
                    expand=True,
                )
                console.print(input_panel)

                key = readchar.readkey()
                if key == readchar.key.UP:
                    if filtered:
                        selected = (selected - 1) % len(filtered)
                elif key == readchar.key.DOWN:
                    if filtered:
                        selected = (selected + 1) % len(filtered)
                elif key in (readchar.key.ENTER, "\r", "\n"):
                    if filtered:
                        return filtered[selected][0]
                    else:
                        return query
                elif key == readchar.key.ESC:
                    return None
                elif key in (readchar.key.BACKSPACE, "\x08", "\x7f"):
                    query = query[:-1]
                    selected = 0
                else:
                    if isinstance(key, str) and len(key) == 1 and key.isprintable():
                        query += key
                        selected = 0

        custom_style = Style.from_dict(
            {
                "frame.border": "#4499ff",
                "frame.label": "#888888",
            }
        )

        text_area = TextArea(prompt=" > ", multiline=False)

        bindings = KeyBindings()

        @bindings.add("enter")
        def _(event):
            event.app.exit(result=text_area.text)

        @bindings.add("c-c")
        @bindings.add("c-d")
        def _(event):
            event.app.exit(result=None)

        @bindings.add("/")
        def _slash_pressed(event):  # type: ignore
            if text_area.text == "":
                event.app.exit(result="__SLASH_MENU__")
            else:
                text_area.buffer.insert_text("/")

        header = Window(
            content=FormattedTextControl(text="  (press / for slash commands)"),
            height=1,
            style="class:frame.label",
        )

        input_frame = Frame(body=HSplit([header, text_area]), style="class:frame")

        app = Application(
            layout=Layout(input_frame),
            key_bindings=bindings,
            style=custom_style,
            full_screen=False,
        )

        while True:
            # 1. Reset input area for the new turn
            text_area.text = ""

            console.print(Rule(style="dim"))

            # Simple prompt without persistent context
            prompt_html = HTML(' <style fg="#4499ff">[Query AI]</style>\n > ')
            text_area.prompt = prompt_html

            try:
                question = app.run()
            except (KeyboardInterrupt, EOFError):
                question = None

            if question is None:
                console.print("\n[yellow]Ending chat session. Goodbye![/yellow]")
                break

            if not question or not question.strip():
                continue

            # '/' keypress triggers the full interactive menu immediately
            if question == "__SLASH_MENU__":
                chosen = interactive_slash_menu()
                if chosen:
                    question = chosen
                else:
                    continue

            if question.strip().lower() in ["exit", "/exit"]:
                console.print("[yellow]Ending chat session. Goodbye![/yellow]")
                break

            if question.strip().startswith("/"):
                cmd_full = question.strip().lower()
                cmd = cmd_full.split()[0]

                if cmd == "/clear":
                    draw_splash()
                elif cmd == "/about":
                    about_text = (
                        "**Query3AI** is an intelligent, Multi-Agent RAG (Retrieval-Augmented Generation) pipeline.\n\n"
                        "It natively builds hierarchical contexts by indexing document chunks directly into a **Neo4j Graph Database**. "
                        "When you ask a question, an internal **Decision Agent** grades relevancy across all documents globally, "
                        "passing the optimal context securely to a **Reasoning Agent** executing on advanced LLM infrastructure (Groq/Ollama)."
                    )
                    content = Group(
                        Text("About Query3AI", style="bold cyan"),
                        Text(""),
                        Markdown(about_text),
                    )
                    console.print(Panel(content, border_style="cyan"))
                elif cmd == "/help":
                    help_table = Table(
                        title="Available Slash Commands", border_style="cyan"
                    )
                    help_table.add_column("Command", style="magenta")
                    help_table.add_column("Description")
                    help_table.add_row(
                        "/about", "Learn about the Query3AI project architecture."
                    )
                    help_table.add_row("/help", "Display this commands menu.")
                    help_table.add_row(
                        "/ingest <path>", "Ingest a document from a local file path."
                    )
                    help_table.add_row(
                        "/listdocs",
                        "List all independent documents currently ingested.",
                    )
                    help_table.add_row(
                        "/list",
                        "Count total Sections and Chunks natively residing in the Neo4j database.",
                    )
                    help_table.add_row(
                        "/deletedoc",
                        "Securely wipe a specific document exactly from the Graph.",
                    )
                    help_table.add_row(
                        "/cleanupdocs", "Delete all documents and clear the database."
                    )
                    help_table.add_row(
                        "/cleanupresorce",
                        "Garbage collect accumulated temporary logs and JSON files explicitly.",
                    )
                    help_table.add_row("/clear", "Clear the terminal screen visually.")
                    help_table.add_row(
                        "/version", "Show the version from pyproject.toml."
                    )
                    help_table.add_row("/exit", "Close the chat application safely.")
                    console.print(help_table)
                elif cmd == "/version":
                    version()
                elif cmd == "/listdocs":
                    list_docs()
                elif cmd.startswith("/ingest"):
                    parts = question.strip().split(maxsplit=1)
                    if len(parts) < 2:
                        console.print("[yellow]Usage: /ingest <file_path>[/yellow]\n")
                        continue
                    file_path = parts[1].strip().strip("\"'")
                    if not os.path.exists(file_path):
                        console.print(
                            f"[red]Error: File not found at '{file_path}'[/red]\n"
                        )
                        continue
                    try:
                        ingest(file_path)
                        all_section_nodes = get_all_nodes()
                        console.print("")
                    except Exception as e:
                        console.print(f"[red]Ingestion Error: {e}[/red]\n")
                elif cmd == "/list":
                    all_section_nodes = get_all_nodes()
                    if all_section_nodes:
                        total_sections = len(all_section_nodes)
                        total_chunks = sum(
                            len(n.get("chunks", [])) for n in all_section_nodes
                        )
                        console.print(
                            f"\n[bold green]Neo4j Database Inventory[/bold green]"
                        )
                        console.print(
                            f"- [cyan]Total Sections:[/cyan] {total_sections}"
                        )
                        console.print(
                            f"- [cyan]Total Chunks:[/cyan]   {total_chunks}\n"
                        )
                    else:
                        console.print("[yellow]Database is currently empty.[/yellow]")
                elif cmd == "/deletedoc":
                    documents = neo4j_client.get_nodes("Document")
                    if not documents:
                        console.print(
                            "[yellow]No documents available in database to delete.[/yellow]\n"
                        )
                        continue

                    doc_options = [
                        (doc.get("doc_id", "Unknown"), doc.get("title", "Untitled"))
                        for doc in documents
                    ]
                    doc_id_to_del = interactive_delete_menu(doc_options)

                    if doc_id_to_del:
                        if confirm_with_border(
                            f"Are you sure you want to delete '{doc_id_to_del}'?"
                        ):
                            delete_document(doc_id_to_del)
                            console.print(f"[green]Deleted {doc_id_to_del}[/green]")
                            all_section_nodes = get_all_nodes()
                elif cmd == "/cleanupdocs":
                    if confirm_with_border("Delete ALL documents?"):
                        neo4j_client.clear_all()
                        console.print("[green]Database cleared.[/green]")
                        all_section_nodes = get_all_nodes()
                elif cmd == "/cleanupresorce" or cmd == "/listpreresource":
                    if not TEMP_OUTPUT_DIR.exists():
                        console.print(
                            "[yellow]No temporary resource directory found.[/yellow]\n"
                        )
                        continue

                    files = list(TEMP_OUTPUT_DIR.glob("*.*"))
                    if not files:
                        console.print(
                            "[yellow]No temporary resources to clean up.[/yellow]\n"
                        )
                        continue

                    if cmd == "/listpreresource":
                        console.print(
                            f"[bold cyan]Temporary Resources ({len(files)} files):[/bold cyan]"
                        )
                        for f in files:
                            console.print(f" - {f.name} ({os.path.getsize(f)} bytes)")
                        console.print("")
                    else:
                        if confirm_with_border(
                            f"Delete {len(files)} temporary resource files?"
                        ):
                            for f in files:
                                try:
                                    os.remove(f)
                                except Exception:
                                    pass
                            console.print(
                                f"[green]Cleaned up {len(files)} files.[/green]\n"
                            )
                else:
                    console.print(
                        f"[yellow]Slash command '{cmd}' is recognized but reserved for future functionality![/yellow]\n"
                    )
                continue

            # After a non-slash query, ask which document to refer to
            documents = neo4j_client.get_nodes("Document")
            if not documents:
                console.print(
                    "[yellow]No documents available. Searching all (empty database)...[/yellow]"
                )
                current_selection = "0"  # Global
            else:
                current_selection = str(
                    interactive_document_menu(
                        documents, f"Select Context for: '{str(question)[:20]}...'", "0"
                    )
                )
                if not current_selection:
                    current_selection = "0"  # Assume Global if escaped or error

            # Prepare target nodes based on persistency
            doc_map = {}
            for idx, doc in enumerate(documents, start=1):
                doc_map[str(idx)] = doc.get("doc_id", f"Doc_{idx}")

            if current_selection == "0":
                target_nodes = get_all_nodes()
                selection_label = "Search All Documents Globally"
            elif current_selection in doc_map:
                doc_id = doc_map[current_selection]
                doc_data = get_nodes(doc_id)
                target_nodes = [sec for chap in doc_data.get("chapters", []) for sec in chap.get("sections", [])] if doc_data else []
                selection_label = doc_id
            else:
                target_nodes = []
                selection_label = "Unknown"

            if not target_nodes:
                console.print("[yellow]No context data found on this target.[/yellow]")
                continue

            console.print(f"[dim]Processing with context: {selection_label}[/dim]")
            console.print(
                f"[dim cyan]🔌 Decision Model: {settings.get_active_decision_model()}[/dim cyan]"
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(
                    description=f"Decision Agent: Searching context...", total=None
                )
                try:
                    filtered_nodes = filter_nodes(question, target_nodes)
                except Exception as e:
                    console.print(f"\n[bold red]Query Error:[/bold red] {e}")
                    continue

            if filtered_nodes:
                preview_data = [
                    {
                        "node_id": n.get("node_id"),
                        "heading": n.get("heading"),
                        "summary": n.get("summary"),
                        "document_name": n.get(
                            "doc_title", n.get("document_name", "Unknown")
                        ),
                        "document_id": n.get("doc_id", "Unknown"),
                    }
                    for n in filtered_nodes
                ]

                console.print("\n[cyan]Decision Agent Extracted Context:[/cyan]")
                json_str = json.dumps(preview_data, indent=2)
                console.print(Panel(JSON(json_str), border_style="yellow", expand=True))

                proceed = confirm_with_border(
                    "\n[bold yellow]Pass this context to Reasoning Model?[/bold yellow]"
                )
                if not proceed:
                    console.print("[dim]Query cancelled.[/dim]\n")
                    continue

            console.print(
                f"\n[dim cyan]🔌 Reasoning Model: {settings.get_active_reasoning_model()}[/dim cyan]"
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(
                    description=f"Reasoning Agent: Thinking...", total=None
                )
                response_text = answer(question, context_nodes=filtered_nodes)

            md_content = Markdown(response_text)
            console.print(Panel(md_content, border_style="green", expand=True))

            if filtered_nodes:
                sources_str = ", ".join(
                    [n.get("heading", "Untitled") for n in filtered_nodes[:3]]
                )
                if len(filtered_nodes) > 3:
                    sources_str += f" (+{len(filtered_nodes)-3} more)"
                console.print(f"[dim]Sources: {sources_str}[/dim]\n")
            else:
                console.print("[dim]Sources: None[/dim]\n")

    except Exception as e:
        handle_error(e)


@app.command("init")
def init(
    local: bool = typer.Option(
        False, "--local", help="Initialize in current directory instead of ~/.query3ai"
    ),
):
    """
    Initialize a new Query3AI workspace. By default, initializes globally in ~/.query3ai.
    Use --local to initialize in the current directory instead.
    """

    if local:
        cwd = os.getcwd()
        compose_path = os.path.join(cwd, "docker-compose.yml")
        config_path = os.path.join(cwd, "config.json")

        compose_content = """version: '3.8'

services:
  neo4j:
    image: neo4j:latest
    container_name: query3ai_neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/query3ai
    volumes:
      - ./neo4j_data:/data
"""
        default_config = {
            "TREE_API_KEY": "",
            "DECISION_API_KEY": "",
            "REASONING_API_KEY": "",
            "TREE_MODEL": "openai/gpt-4o",
            "DECISION_MODEL": "openai/gpt-4o-mini",
            "REASONING_MODEL": "openai/o3-mini",
            "TREE_API_BASE": "",
            "DECISION_API_BASE": "",
            "REASONING_API_BASE": "",
            "QUERY3AI_CHUNK_SIZE": "500",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "query3ai",
            "TREE_SYSTEM_PROMPT": DEFAULT_TREE_PROMPT,
            "DECISION_SYSTEM_PROMPT": DEFAULT_DECISION_PROMPT,
            "REASONING_SYSTEM_PROMPT": DEFAULT_REASONING_PROMPT,
        }

        try:
            if not os.path.exists(compose_path):
                with open(compose_path, "w") as f:
                    f.write(compose_content)
                console.print(f"[green]Created {compose_path}[/green]")
            else:
                console.print(
                    f"[yellow]Skipped {compose_path} (already exists)[/yellow]"
                )

            if not os.path.exists(config_path):
                with open(config_path, "w") as f:
                    json.dump(default_config, f, indent=4)
                console.print(f"[green]Created {config_path}[/green]")
            else:
                console.print(
                    f"[yellow]Skipped {config_path} (already exists)[/yellow]"
                )

            success_msg = (
                "Workspace initialized in current directory!\n\n"
                "1. Run [bold cyan]docker-compose up -d[/bold cyan] to start Neo4j.\n"
                "2. Edit [bold cyan]config.json[/bold cyan] to customize models, prompts, and API keys.\n"
                "3. Run [bold cyan]query3ai chat[/bold cyan] to begin."
            )
            console.print(
                Panel(success_msg, title="Setup Complete", border_style="green")
            )
        except Exception as e:
            handle_error(e)
        return

    ensure_workspace()

    compose_content = """version: '3.8'

services:
  neo4j:
    image: neo4j:latest
    container_name: query3ai_neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/query3ai
    volumes:
      - ./neo4j_data:/data
"""

    default_config = {
        "TREE_API_KEY": "",
        "DECISION_API_KEY": "",
        "REASONING_API_KEY": "",
        "TREE_MODEL": "openai/gpt-4o",
        "DECISION_MODEL": "openai/gpt-4o-mini",
        "REASONING_MODEL": "openai/o3-mini",
        "TREE_API_BASE": "",
        "DECISION_API_BASE": "",
        "REASONING_API_BASE": "",
        "QUERY3AI_CHUNK_SIZE": "500",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "query3ai",
        "TREE_SYSTEM_PROMPT": DEFAULT_TREE_PROMPT,
        "DECISION_SYSTEM_PROMPT": DEFAULT_DECISION_PROMPT,
        "REASONING_SYSTEM_PROMPT": DEFAULT_REASONING_PROMPT,
    }

    try:
        if not COMPOSE_PATH.exists():
            with open(COMPOSE_PATH, "w") as f:
                f.write(compose_content)
            console.print(f"[green]Created {COMPOSE_PATH}[/green]")
        else:
            console.print(f"[yellow]Skipped {COMPOSE_PATH} (already exists)[/yellow]")

        if not CONFIG_PATH.exists():
            with open(CONFIG_PATH, "w") as f:
                json.dump(default_config, f, indent=4)
            console.print(f"[green]Created {CONFIG_PATH}[/green]")
        else:
            console.print(f"[yellow]Skipped {CONFIG_PATH} (already exists)[/yellow]")

        success_msg = (
            f"Global workspace initialized in [bold]{WORKSPACE_DIR}[/bold]!\n\n"
            "1. Edit [bold cyan]~/.query3ai/config.json[/bold cyan] to customize models, prompts, and API keys.\n"
            "2. Run [bold cyan]query3ai start-db[/bold cyan] to start Neo4j.\n"
            "3. Run [bold cyan]query3ai chat[/bold cyan] to begin from anywhere!"
        )
        console.print(Panel(success_msg, title="Setup Complete", border_style="green"))
    except Exception as e:
        handle_error(e)


@app.command("start-db")
def start_db():
    """
    Start the global Neo4j database.
    """

    if not COMPOSE_PATH.exists():
        console.print(
            "[red]Global workspace not initialized. Please run 'query3ai init' first.[/red]"
        )
        return

    try:
        console.print(
            f"[cyan]Starting Neo4j via docker-compose from {COMPOSE_PATH}...[/cyan]"
        )
        subprocess.run(
            ["docker-compose", "-f", str(COMPOSE_PATH), "up", "-d"], check=True
        )
        console.print("[green]Neo4j started successfully![/green]")
    except FileNotFoundError:
        try:
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_PATH), "up", "-d"], check=True
            )
            console.print("[green]Neo4j started successfully![/green]")
        except Exception as err:
            console.print(f"[red]Failed to start database: {err}[/red]")
            console.print("[yellow]Ensure Docker is running on your machine.[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to start database: {e}[/red]")


@app.command("stop-db")
def stop_db():
    """
    Stop the global Neo4j database.
    """

    if not COMPOSE_PATH.exists():
        console.print(
            "[red]Global workspace not initialized. Please run 'query3ai init' first.[/red]"
        )
        return

    try:
        console.print(
            f"[cyan]Stopping Neo4j via docker-compose from {COMPOSE_PATH}...[/cyan]"
        )
        subprocess.run(["docker-compose", "-f", str(COMPOSE_PATH), "down"], check=True)
        console.print("[green]Neo4j stopped successfully![/green]")
    except FileNotFoundError:
        try:
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_PATH), "down"], check=True
            )
            console.print("[green]Neo4j stopped successfully![/green]")
        except Exception as err:
            console.print(f"[red]Failed to stop database: {err}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to stop database: {e}[/red]")


@app.command("version")
def version():
    """Show the currently installed version of Query3AI (retrieved from pyproject.toml)."""
    try:
        # Find pyproject.toml relative to this file:
        # src/query3ai/cli/commands.py -> ../../../pyproject.toml
        current_file = Path(__file__).resolve()
        project_root = current_file.parents[3]
        toml_path = project_root / "pyproject.toml"

        if not toml_path.exists():
            console.print(
                "[yellow]Warning: pyproject.toml not found in repository root. Is it installed in editable mode?[/yellow]"
            )
            # Fallback to metadata
            import importlib.metadata

            try:
                ver = importlib.metadata.version("query3ai")
                console.print(
                    f"Query3AI version: [bold cyan]{ver}[/bold cyan] (via metadata)"
                )
                return
            except Exception:
                console.print("[red]Error: Could not determine version.[/red]")
                return

        with open(toml_path, "r") as f:
            content = f.read()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                console.print(
                    f"Query3AI version: [bold cyan]{match.group(1)}[/bold cyan]"
                )
            else:
                console.print(
                    "[red]Error: Could not find version string in pyproject.toml.[/red]"
                )

    except Exception as e:
        console.print(f"[red]Error reading version: {e}[/red]")
