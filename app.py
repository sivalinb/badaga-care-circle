#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from badaga_care.config import ROOT, Settings
from badaga_care.service import CareService
from badaga_care.ui import CSS, build_demo
import gradio as gr


def main():
    parser = argparse.ArgumentParser(description="Run the fictional Badaga Care Circle demo locally.")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--open", action="store_true", help="Open a browser tab")
    args = parser.parse_args()
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    settings = Settings.from_env()
    svc = CareService(settings)
    demo = build_demo(svc)
    demo.queue(default_concurrency_limit=4, max_size=32).launch(
        server_name="127.0.0.1", server_port=args.port, share=False, inbrowser=args.open,
        theme=gr.themes.Soft(primary_hue="teal", neutral_hue="slate"), css=CSS,
        show_error=False, footer_links=[],
        blocked_paths=[str(ROOT / ".env"), str(settings.data_dir)],
        max_file_size="1mb", strict_cors=True,
    )


if __name__ == "__main__":
    main()
