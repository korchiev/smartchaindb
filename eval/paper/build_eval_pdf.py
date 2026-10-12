#!/usr/bin/env python3
"""Compile eval/paper/evaluation.tex and copy the PDF to eval/SmartChainDB_evaluation.pdf.

Uses tectonic if available (it fetches LaTeX packages on demand), otherwise
latexmk/pdflatex. Regenerate figures first with eval/plot_professor_figures.py.
"""
from __future__ import print_function

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "evaluation.tex")
PDF = os.path.join(HERE, "evaluation.pdf")
COPY = os.path.abspath(os.path.join(HERE, "..", "SmartChainDB_evaluation.pdf"))


def find_tectonic():
    found = shutil.which("tectonic")
    if found:
        return found
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "tectonic", "tectonic.exe")
    return local if os.path.exists(local) else None


def build():
    tectonic = find_tectonic()
    if tectonic:
        cmd = [tectonic, TEX, "--outdir", HERE]
    elif shutil.which("latexmk"):
        cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir=" + HERE, TEX]
    else:
        sys.exit("need tectonic or latexmk on PATH")
    subprocess.check_call(cmd, cwd=HERE)
    shutil.copyfile(PDF, COPY)
    print("wrote", PDF)
    print("copied to", COPY)


if __name__ == "__main__":
    build()
