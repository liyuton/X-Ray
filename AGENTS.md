# Repository Guidelines

## Project Structure & Module Organization
Core pipeline scripts live in `src/`. Most are standalone Python entry points for generating yearly GML slices, skeleton trees, entropy metrics, and final X-ray visualizations. Native parsing code for `readgml` lives in `src/readgml/`. Input datasets belong in `input/source_gml/`. Generated artifacts are written to `temp_files/` and `output/`; treat both as build outputs, not hand-edited source. Lightweight validation scripts live in `test/`, with a few older `test_*.py` helpers still kept under `src/`.

## Build, Test, and Development Commands
Install dependencies from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the main pipeline from `src/` because many scripts use `../temp_files` and `../output` relative paths:

```bash
cd src
python gen_intermediate_files.py
python ilf_fitting.py
python main.py
python gen_vd_and_dpi.py
python pattern_statistics.py
```

If the local `readgml` extension is missing or incompatible, rebuild it with:

```bash
cd src/readgml
python setup.py build_ext --inplace
```

For the Elasticsearch export utility, run `python test/es_filter_high_citation.py --help` or `python src/es_filter_high_citation.py --help`.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, `snake_case` for files, functions, and variables, and `UPPER_CASE` for module constants. Keep scripts runnable as direct entry points with `if __name__ == "__main__":`. Prefer small, single-purpose functions over expanding monolithic loops. No formatter or linter config is checked in, so match surrounding code and keep imports and argument names stable.

## Testing Guidelines
There is no centralized `pytest` suite yet. Validate changes by running the specific script you touched on a small PID set and checking the expected files under `temp_files/` or `output/`. Name new checks `test_<feature>.py` and place them in `test/` unless they are tightly coupled to a `src/` script.

## Commit & Pull Request Guidelines
Recent history uses short imperative subjects such as `add`, `update`, and `change readme`. Keep that imperative style, but make it specific, for example `add dpi summary export`. PRs should state which pipeline stage changed, list required input data or environment assumptions, and include sample output paths or screenshots when visualization results change. Avoid committing bulky generated artifacts unless the change is explicitly about reference outputs.

## Execution Principles

- **Think before coding**: Explore the relevant code paths before editing, state assumptions and ambiguities explicitly, surface tradeoffs when more than one interpretation is plausible, and stop for clarification instead of guessing when uncertainty would change the implementation.
- **Keep changes minimal and goal-driven**: Define a short success criterion for the task, prefer the simplest implementation that satisfies it, and make only the edits that are directly required. Do not add speculative abstractions, adjacent cleanup, or extra configurability that was not requested.
- **Document code clearly**: Add concise, standardized comments and docstrings where they materially improve understanding of functions, modules, or non-obvious logic. Do not add comment noise to self-explanatory code, but leave modified code easier to read than before.
- **Validate and recap every change**: After each substantive modification, verify the affected behavior with the most relevant check available, then provide a brief recap of both the conversation outcome and the code changes. When code was modified, also summarize the touched modules at a high level.
- **Use the correct Python runtime**: When running Python code in this workspace, activate the `xray` Conda environment with `conda activate xray` unless the task explicitly requires another environment. When updating contributor-facing setup docs, keep the repository's documented `uv` workflow unless the user asks to change it.