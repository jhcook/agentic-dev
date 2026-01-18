import logging
import subprocess
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, List, Set

import click

from agent.core.graph import build_from_repo
from agent.utils.text import sanitize_mermaid_label

# Configure logging
logger = logging.getLogger(__name__)

def get_repo_url() -> str:
    """Gets the repository's remote URL and formats it for file linking."""
    try:
        # Get remote URL
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"], text=True
        ).strip()
        
        # Format for GitHub/GitLab (https/ssh)
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]
        if remote_url.startswith("git@"):
            remote_url = remote_url.replace(":", "/").replace("git@", "https://")
        
        # Get current branch
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
        ).strip()
        
        return f"{remote_url}/blob/{branch}/"
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Could not determine git repository URL. File links will be disabled.")
        return ""

def generate_mermaid_graph(graph: Dict[str, List[Dict[str, Any]]], repo_base_url: str) -> str:
    """Generates the Mermaid syntax string from the graph data."""
    output = ["graph TD"]
    
    # Define styles for different node types
    output.append("    classDef plan fill:#e6f7ff,stroke:#91d5ff,stroke-width:2px")
    output.append("    classDef story fill:#f6ffed,stroke:#b7eb8f,stroke-width:2px")
    output.append("    classDef runbook fill:#fffbe6,stroke:#ffe58f,stroke-width:2px")
    output.append("    classDef code fill:#f0f0f0,stroke:#d9d9d9,stroke-width:2px")

    nodes_by_id = {node['id']: node for node in graph['nodes']}
    
    for node in graph['nodes']:
        node_id = node['id']
        sanitized_title = sanitize_mermaid_label(node.get('title', ''))
        label = f'{node_id}<br/><i>{sanitized_title}</i>'
        output.append(f'    {node_id}["{label}"]')
        output.append(f'    class {node_id} {node["type"]}')
        
        if repo_base_url and 'path' in node:
            url = f"{repo_base_url}{node['path']}"
            output.append(f'    click {node_id} "{url}" "View File"')

    for edge in graph['edges']:
        # Ensure both source and target nodes exist before creating an edge
        if edge['source'] in nodes_by_id and edge['target'] in nodes_by_id:
            output.append(f"    {edge['source']} --> {edge['target']}")
        else:
            logger.warning(f"Skipping edge from non-existent node: {edge['source']} -> {edge['target']}")

    return "\n".join(output)

def serve_html(html_content: str):
    """Starts a local web server to display the HTML content."""
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))

    # CRITICAL: Bind only to localhost (loopback interface only, not network)
    server_address = ('127.0.0.1', 8000)
    httpd = HTTPServer(server_address, Handler)
    
    url = f"http://{server_address[0]}:{server_address[1]}"
    print(f"Serving visualization at {url}")
    print("Press Ctrl+C to stop the server.")

    # Open in browser
    webbrowser.open(url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        httpd.server_close()

@click.group()
def visualize():
    """Generates diagrammatic views of project artifacts."""
    pass

@visualize.command()
@click.option('--serve', is_flag=True, help="Serve the graph in a local web browser.")
@click.option('--verbose', is_flag=True, help="Enable verbose logging to stderr.")
def graph(serve: bool, verbose: bool):
    """Generate a full dependency graph of all project artifacts."""
    start_time = time.time()
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s', stream=click.get_text_stream('stderr'))
    
    project_graph = build_from_repo('.')
    repo_url = get_repo_url()
    
    mermaid_content = generate_mermaid_graph(project_graph, repo_url)
    
    if serve:
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Project Visualization</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            </style>
        </head>
        <body>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>mermaid.initialize({{ startOnLoad: true }});</script>
            <div class="mermaid">{mermaid_content}</div>
        </body>
        </html>
        """
        serve_html(html_content)
    else:
        print(mermaid_content)
        
    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000
    node_count = len(project_graph['nodes'])
    edge_count = len(project_graph['edges'])
    click.echo(
        f"Generated graph with {node_count} nodes and {edge_count} edges in {duration_ms:.2f}ms",
        err=True
    )

@visualize.command()
@click.argument('story_id')
@click.option('--verbose', is_flag=True, help="Enable verbose logging to stderr.")
def flow(story_id: str, verbose: bool):
    """Show the specific flow for a single story."""
    start_time = time.time()
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s', stream=click.get_text_stream('stderr'))

    full_graph = build_from_repo('.')
    nodes_by_id = {node['id']: node for node in full_graph['nodes']}
    
    if story_id not in nodes_by_id:
        click.echo(f"Error: Story '{story_id}' not found.", err=True)
        exit(1)

    # Filtering logic
    nodes_to_keep: Set[str] = {story_id}
    edges_to_keep: List[Dict[str, str]] = []
    
    # Find parent plan, child runbooks, and linked code files
    runbook_ids = set()
    for edge in full_graph['edges']:
        # Parent Plan -> Story
        if edge['target'] == story_id:
            nodes_to_keep.add(edge['source'])
            edges_to_keep.append(edge)
        # Story -> Runbook
        elif edge['source'] == story_id:
            nodes_to_keep.add(edge['target'])
            edges_to_keep.append(edge)
            runbook_ids.add(edge['target'])
    
    # Runbook -> Code
    for edge in full_graph['edges']:
        if edge['source'] in runbook_ids:
            nodes_to_keep.add(edge['target'])
            edges_to_keep.append(edge)
            
    filtered_nodes = [node for node in full_graph['nodes'] if node['id'] in nodes_to_keep]
    
    flow_graph = {
        "nodes": filtered_nodes,
        "edges": edges_to_keep
    }

    repo_url = get_repo_url()
    mermaid_content = generate_mermaid_graph(flow_graph, repo_url)
    print(mermaid_content)

    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000
    node_count = len(flow_graph['nodes'])
    edge_count = len(flow_graph['edges'])
    click.echo(
        f"Generated flow with {node_count} nodes and {edge_count} edges in {duration_ms:.2f}ms",
        err=True
    )