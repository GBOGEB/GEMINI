import os
import yaml

class BLSNEngine:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.project_name = self.config['project_name']
        self.metrics = self.config['monitored_metrics']

    def generate_ascii_dashboard(self):
        """Generates a scannable ASCII text block for quick logs visualization."""
        border = "=" * 50
        lines = [border, f" BLSN REPO DASHBOARD: {self.project_name}", border]
        for metric in self.metrics:
            lines.append(f" [{metric['id']}] {metric['description'][:40]}... -> Status: {metric['status']}")
        lines.append(border)
        return "\n".join(lines)

    def generate_mermaid_diagram(self):
        """Generates an explicit Mermaid chart mapping the data lineage."""
        mermaid_code = ["graph TD", "    SSOT[(YAML Configuration)] -->|Parses| Engine[BLSN Python Engine]"]
        for metric in self.metrics:
            mermaid_code.append(f"    Engine -->|Validates| {metric['id']}[{metric['id']}: {metric['status']}]")
        mermaid_code.append("    Engine -->|Compiles| HTML[Interactive HTML Report]")
        return "\n".join(mermaid_code)

    def generate_html_report(self, ascii_dash, mermaid_graph):
        """Compiles clean, highly structured HTML for downstream engineering reviews."""
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.project_name} - 2nd Opinion Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; background-color: #f8f9fa; color: #333; }}
        h1, h2 {{ color: #0056b3; }}
        pre {{ background: #ebebeb; padding: 15px; border-left: 5px solid #0056b3; font-family: monospace; }}
        .card {{ background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    </style>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
    </script>
</head>
<body>
    <h1>Project Baseline: {self.project_name}</h1>
    <div class="card">
        <h2>ASCII Lineage Status</h2>
        <pre>{ascii_dash}</pre>
    </div>
    <div class="card">
        <h2>Mermaid Lineage Graph</h2>
        <pre class="mermaid">
{mermaid_graph}
        </pre>
    </div>
</body>
</html>
"""
        return html_template

    def run(self, output_dir="output"):
        os.makedirs(output_dir, exist_ok=True)
        
        # Build artifacts
        ascii_dash = self.generate_ascii_dashboard()
        mermaid_graph = self.generate_mermaid_diagram()
        html_content = self.generate_html_report(ascii_dash, mermaid_graph)
        
        # Idempotent write operations
        with open(os.path.join(output_dir, "report.html"), "w") as f:
            f.write(html_content)
        with open(os.path.join(output_dir, "architecture.mermaid"), "w") as f:
            f.write(mermaid_graph)
            
        print(f"--> BLSN Engine successfully executed. Artifacts written to code-driven directory: '{output_dir}/'")

# Driver execution block for local notebook environments
if __name__ == "__main__":
    # Simulated file instantiation for standalone execution execution
    os.makedirs("config", exist_ok=True)
    if not os.path.exists("config/blsn_config.yaml"):
        print("Error: Please write config/blsn_config.yaml first.")
    else:
        engine = BLSNEngine("config/blsn_config.yaml")
        engine.run()
