import os
import json
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

from services.document_service import extract_text, chunk_text  # type: ignore
from services.reasoning_service import answer  # type: ignore
from services.tree_service import build_tree  # type: ignore
from services.decision_service import filter_nodes  # type: ignore
from services.graph_service import store_tree, get_nodes, get_all_nodes, delete_document  # type: ignore
from db.neo4j_client import neo4j_client  # type: ignore
from config.settings import settings  # type: ignore

app = typer.Typer(help="Query3AI - Intelligent document query system")
console = Console()


def handle_error(e: Exception):
    err_str = str(e).lower()
    if "connection refused" in err_str and "11434" in err_str:
        console.print(
            "[bold red]API Error:[/bold red] Ollama connection failed. [yellow]Start Ollama with: ollama serve[/yellow]"
        )
    elif "not found" in err_str and "model" in err_str:
        console.print(
            f"[bold red]Model Error:[/bold red] Model not pulled. [yellow]Run: ollama pull <model_name>[/yellow]\n[dim]Details: {e}[/dim]"
        )
    elif (
        "serviceunavailable" in err_str or "neo4j" in err_str or "connection" in err_str
    ):
        console.print(
            f"[bold red]DB Error:[/bold red] Neo4j connection failed. Please verify URI and credentials.\n[dim]Details: {e}[/dim]"
        )
    else:
        console.print(Panel(str(e), title="Error", border_style="red"))


@app.command("ingest")
def ingest(
    file_path: str,
    cloud: bool = typer.Option(
        False, "--cloud", help="Enable to switch to cloud-only processing tools."
    ),
):
    """
    Ingest a document, extract text, chunk it, build tree, and store in Neo4j.
    """
    if cloud:
        settings.USE_CLOUD = True

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
        sections = data.get("sections", [])

        tree = Tree(
            f"[bold magenta]📄 {doc_info.get('title', 'Unknown Title')}[/bold magenta] (ID: {doc_info.get('doc_id')})"
        )

        for sec in sections:
            sec_branch = tree.add(
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


def interactive_document_menu(documents: list, question: str) -> str | None:
    """Show the interactive document selection menu using readchar and up/down arrows."""
    options = [("0", "Search All Documents Globally")]
    for idx, doc in enumerate(documents, start=1):
        doc_id = doc.get("doc_id", f"Doc_{idx}")
        title = doc.get("title", doc_id)
        options.append((str(idx), f"{title} ({doc_id})"))

    selected = 0

    while True:
        console.clear()
        console.print(Rule(style="dim"))
        console.print(f"[bold blue]Active Query:[/bold blue] {question}")
        console.print("\n[bold cyan]Select Target Document Context:[/bold cyan]")

        try:
            term_width = int(os.get_terminal_size().columns)
        except Exception:
            term_width = 80

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

        console.print(
            Panel(
                Group(*body),
                border_style="cyan",
                padding=(0, 1),
                expand=True,
            )
        )

        console.print(
            "\n[dim]  ↑↓ to navigate  · Enter to select  · Esc to cancel[/dim]"
        )

        key = readchar.readkey()
        if key == readchar.key.UP:
            selected = (selected - 1) % len(options)
        elif key == readchar.key.DOWN:
            selected = (selected + 1) % len(options)
        elif key in (readchar.key.ENTER, "\r", "\n"):
            return options[selected][0]
        elif key == readchar.key.ESC:
            return None


@app.command("ask")
def ask(
    question: str,
    cloud: bool = typer.Option(
        False, "--cloud", help="Enable to switch to cloud-only processing tools."
    ),
):
    """
    Ask a question based on ingested documents.
    """
    if cloud:
        settings.USE_CLOUD = True

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
            target_nodes = doc_data.get("sections", []) if doc_data else []
        else:
            console.print("[red]Invalid selection. Exiting object graph.[/red]")
            return

        if not target_nodes:
            console.print("[yellow]No valid sections found in selection.[/yellow]")
            return

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

            proceed = Confirm.ask(
                "\n[bold yellow]Do you want to pass this exact compiled context to the Reasoning Model?[/bold yellow]"
            )
            if not proceed:
                console.print("[dim]Query canceled cleanly.[/dim]\n")
                return

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
        console.print(Panel(response_text, border_style="blue"))

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
    should_delete = Confirm.ask(f"Are you sure you want to delete document '{doc_id}'?")
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
def chat(
    cloud: bool = typer.Option(
        False, "--cloud", help="Enable to switch to cloud-only processing tools."
    )
):
    """
    Start an interactive chat session based on ingested documents.
    """
    if cloud:
        settings.USE_CLOUD = True

    try:
        all_section_nodes = get_all_nodes()
        if not all_section_nodes:
            console.print(
                "[yellow]No documents ingested yet. Please run 'ingest' first.[/yellow]"
            )
            return

        os.system("cls" if os.name == "nt" else "clear")
        console.print("[bold green]Welcome to Query3AI Interactive Chat![/bold green]")
        console.print(
            "[dim]Type '/help' to see all available console commands.[/dim]\n"
        )

        from prompt_toolkit import prompt  # type: ignore
        from prompt_toolkit.keys import Keys  # type: ignore
        from prompt_toolkit.key_binding import KeyBindings  # type: ignore
        from prompt_toolkit.styles import Style  # type: ignore
        from prompt_toolkit.formatted_text import HTML  # type: ignore
        import sys

        SLASH_COMMANDS = [
            ("/about", "Learn about Query3AI Interactive Chat."),
            ("/help", "Display usage and commands."),
            ("/ingest", "Ingest a new document from a specified file path."),
            ("/listdocs", "List indexed documentation."),
            ("/list", "List available assets."),
            ("/deletedoc", "Remove a specific document from the database."),
            ("/cleanupdocs", "Delete all documents from the database."),
            ("/cleanupresorce", "Clean up temporary logs and JSON files."),
            ("/clear", "Clear chat history."),
            ("/exit", "Exit the interactive session."),
        ]

        def print_input_box_top():
            """Draw the top boundary of the input box."""
            try:
                w = int(os.get_terminal_size().columns)
            except Exception:
                w = 80
            console.print(f"[blue]\u256d{'\u2500' * (w - 2)}\u256e[/blue]")
            console.print(
                f"[blue]\u2502[/blue]  [dim](press / for slash commands)[/dim]"
            )

        def interactive_slash_menu() -> str | None:
            """Show the slash command menu and return selected command or None."""
            query = "/"
            selected = 0

            while True:
                # Clear and redraw
                console.clear()
                console.print(
                    "[bold green]Welcome to Query3AI Interactive Chat![/bold green]"
                )
                console.print(
                    "[dim]Type '/help' to see all available console commands.[/dim]\n"
                )

                try:
                    term_width = int(os.get_terminal_size().columns)
                except Exception:
                    term_width = 80

                # Draw pseudo input box wrapping the query
                console.print(f"[blue]\u256d{'\u2500' * (term_width - 2)}\u256e[/blue]")
                console.print(
                    f"[blue]\u2502[/blue]  [dim](press / for slash commands)[/dim]"
                )
                console.print(f"[blue]\u2502[/blue] > {query}[blink]_[/blink]")
                console.print(
                    f"[blue]\u2570{'\u2500' * (term_width - 2)}\u256f[/blue]\n"
                )

                # Filter commands
                filtered = [c for c in SLASH_COMMANDS if c[0].startswith(query.lower())]

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

                    console.print(Rule(style="dim"))
                    console.print(
                        Panel(
                            Group(*body),
                            border_style="green",
                            padding=(0, 1),
                            expand=True,
                        )
                    )
                else:
                    console.print(Rule(style="dim"))
                    console.print(
                        f"[dim]No commands match '{query}' — will be sent as regular message.[/dim]"
                    )

                console.print(
                    "\n[dim]  ↑↓ to navigate  · Enter to select  · Esc to cancel  · Type to search[/dim]"
                )

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

        custom_style = Style.from_dict(
            {
                "prompt": "#4499ff bold",
                "bottom-toolbar": "#555555 bg:default",
            }
        )

        def bottom_toolbar():
            try:
                w = int(os.get_terminal_size().columns)
            except Exception:
                w = 80
            return HTML(
                f'<style fg="ansiblue">\u2570{"\u2500" * (w - 2)}\u256f</style>'
            )

        bindings = KeyBindings()

        @bindings.add("/")
        def _slash_pressed(event):  # type: ignore
            event.app.exit(result="__SLASH_MENU__")

        while True:
            console.print(Rule(style="dim"))
            print_input_box_top()
            try:
                question = prompt(
                    HTML('<style fg="ansiblue">\u2502</style> > '),
                    style=custom_style,
                    bottom_toolbar=bottom_toolbar,
                    key_bindings=bindings,
                )
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
                cmd = question.strip().lower()
                if cmd == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    console.print(
                        "[bold green]Welcome to Query3AI Interactive Chat![/bold green]"
                    )
                    console.print(
                        "[dim]Type '/help' to see all available console commands.[/dim]\n"
                    )
                elif cmd == "/about":
                    about_text = (
                        "**Query3AI** is an intelligent, Multi-Agent RAG (Retrieval-Augmented Generation) pipeline.\n\n"
                        "It natively builds hierarchical contexts by indexing document chunks directly into a **Neo4j Graph Database**. "
                        "When you ask a question, an internal **Decision Agent** grades relevancy across all documents globally, "
                        "passing the optimal context securely to a **Reasoning Agent** executing on advanced LLM infrastructure (Groq/Ollama)."
                    )

                    console.print(
                        Panel(
                            Markdown(about_text),
                            title="About Query3AI",
                            border_style="cyan",
                        )
                    )
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
                        "/cleanupdocs",
                        "Delete all documents and clear the database.",
                    )
                    help_table.add_row(
                        "/cleanupresorce",
                        "Garbage collect accumulated temporary logs and JSON files explicitly.",
                    )
                    help_table.add_row("/clear", "Clear the terminal screen visually.")
                    help_table.add_row("/exit", "Close the chat application safely.")
                    console.print(help_table)
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
                        # Refresh nodes after successful ingestion
                        all_section_nodes = get_all_nodes()
                        console.print("")  # spacing
                    except Exception as e:
                        console.print(f"[red]Ingestion Error: {e}[/red]\n")
                elif cmd == "/list":
                    # Refreshing nodes globally catching newly extracted inputs seamlessly.
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

                    def interactive_delete_menu() -> str | None:
                        query = ""
                        selected = 0
                        while True:
                            console.clear()
                            console.print(
                                "[bold red]Delete Document Selection[/bold red]"
                            )
                            console.print(
                                "[dim]Type to filter documents by ID/Title...[/dim]\n"
                            )

                            try:
                                term_width = int(os.get_terminal_size().columns)
                            except Exception:
                                term_width = 80

                            console.print(
                                f"[red]\u256d{'\u2500' * (term_width - 2)}\u256e[/red]"
                            )
                            console.print(
                                f"[red]\u2502[/red] > {query}[blink]_[/blink]"
                            )
                            console.print(
                                f"[red]\u2570{'\u2500' * (term_width - 2)}\u256f[/red]\n"
                            )

                            filtered = [
                                (d_id, d_title)
                                for d_id, d_title in doc_options
                                if query.lower() in d_id.lower()
                                or query.lower() in d_title.lower()
                            ]

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
                                        lines.append(
                                            Text(f"   {padded}  ", style="dim white")
                                        )

                                body = []
                                for i, line in enumerate(lines):
                                    body.append(line)
                                    if i < len(lines) - 1:
                                        body.append(Text(""))

                                console.print(Rule(style="dim red"))
                                console.print(
                                    Panel(
                                        Group(*body),
                                        border_style="red",
                                        padding=(0, 1),
                                        expand=True,
                                    )
                                )
                            else:
                                console.print(Rule(style="dim red"))
                                console.print(
                                    f"[dim]No documents match '{query}' — will use exact string.[/dim]"
                                )

                            console.print(
                                "\n[dim]  ↑↓ to navigate  · Enter to select  · Esc to cancel  · Type to search[/dim]"
                            )

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
                                if (
                                    isinstance(key, str)
                                    and len(key) == 1
                                    and key.isprintable()
                                ):
                                    query += key
                                    selected = 0

                    doc_id = interactive_delete_menu()
                    console.clear()

                    if not doc_id or not doc_id.strip():
                        console.print("[dim]Deletion cancelled.[/dim]\n")
                        continue

                    should_delete = Confirm.ask(
                        f"[bold red]WARNING: Are you sure you want to permanently delete document '{doc_id}' and all matching chunks from the database?[/bold red]"
                    )
                    if should_delete:
                        # Refresh node memory explicitly bypassing legacy cached arrays locally!

                        try:
                            delete_document(doc_id)
                            console.print(
                                f"[bold green]Successfully disconnected '{doc_id}' exactly from Neo4j![/bold green]\n"
                            )
                            # Refresh node memory explicitly bypassing legacy cached arrays locally!
                            all_section_nodes = get_all_nodes()
                        except Exception as e:
                            console.print(f"[bold red]Delete Error:[/bold red] {e}\n")
                    else:
                        console.print(
                            "[dim]Deletion efficiently cancelled strictly protecting elements natively.[/dim]\n"
                        )
                elif cmd == "/cleanupdocs":
                    should_delete = Confirm.ask(
                        f"[bold red]WARNING: Are you sure you want to permanently delete ALL documents from the database?[/bold red]"
                    )
                    if should_delete:
                        try:
                            neo4j_client.clear_all()
                            console.print(
                                f"[bold green]Successfully deleted all documents from Neo4j![/bold green]\n"
                            )
                            all_section_nodes = get_all_nodes()
                        except Exception as e:
                            console.print(f"[bold red]Delete Error:[/bold red] {e}\n")
                    else:
                        console.print(
                            "[dim]Deletion efficiently cancelled strictly protecting elements natively.[/dim]\n"
                        )
                elif cmd == "/cleanupresorce":
                    temp_dir = os.path.join(os.getcwd(), "temp_output")
                    if os.path.exists(temp_dir):
                        files = [
                            f
                            for f in os.listdir(temp_dir)
                            if (f.startswith("related_nodes_") and f.endswith(".json"))
                            or (f.startswith("debug") and f.endswith(".txt"))
                        ]
                        if not files:
                            console.print(
                                "[yellow]No valid temporary logs or debug files found in the active directory.[/yellow]\n"
                            )
                        else:
                            should_del = Confirm.ask(
                                f"\n[bold red]Safeguard: Delete {len(files)} temporary logs and debug files from file system?[/bold red]"
                            )
                            if should_del:
                                try:
                                    for f in files:
                                        os.remove(os.path.join(temp_dir, f))
                                    console.print(
                                        f"[bold green]Successfully garbage collected {len(files)} temporary files![/bold green]\n"
                                    )
                                except Exception as e:
                                    console.print(
                                        f"[bold red]Delete Error:[/bold red] {e}\n"
                                    )
                            else:
                                console.print(
                                    "[dim]File Cleanup explicitly prevented respecting User Safeguard rules.[/dim]\n"
                                )
                    else:
                        console.print(
                            "[dim]No temporary directory formally initialized yet.[/dim]\n"
                        )
                else:
                    console.print(
                        f"[yellow]Slash command '{cmd}' is recognized but reserved for future functionality![/yellow]\n"
                    )
                continue

            documents = neo4j_client.get_nodes("Document")
            if not documents:
                console.print("[yellow]No documents available in database.[/yellow]")
                continue

            console.print("\n[bold cyan]Select Target Document for Query:[/bold cyan]")
            console.print("[0] Search All Documents Globally")
            doc_map = {}
            for idx, doc in enumerate(documents, start=1):
                doc_id = doc.get("doc_id", f"Doc_{idx}")
                doc_map[str(idx)] = doc_id

            selection = interactive_document_menu(documents, question)

            if selection is None:
                console.print("[dim]Selection cancelled. Returning to prompt.[/dim]\n")
                continue

            if selection == "0":
                target_nodes = get_all_nodes()
            elif selection in doc_map:
                doc_data = get_nodes(doc_map[selection])
                target_nodes = doc_data.get("sections", []) if doc_data else []
            else:
                console.print("[red]Invalid selection! Cancelling execution.[/red]")
                continue

            # Clear UI to restore normal chat formatting after escaping the fullscreen menu
            console.clear()
            console.print(f"[bold blue]Active Query:[/bold blue] {question}\n")

            if not target_nodes:
                console.print("[yellow]No context data found on this target.[/yellow]")
                continue

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task(
                    description=f"Decision Agent: Searching context with {settings.get_active_decision_model()}...",
                    total=None,
                )

                try:
                    # Decision Agent
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

                proceed = Confirm.ask(
                    "\n[bold yellow]Do you want to pass this exact compiled context to the Reasoning Model?[/bold yellow]"
                )
                if not proceed:
                    console.print("[dim]Query cancelled. Returning to prompt.[/dim]\n")
                    continue

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task(
                    description=f"Reasoning Agent: Thinking with {settings.get_active_reasoning_model()}...",
                    total=None,
                )

                # Reasoning Agent
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
