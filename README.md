# leonida-progress

**Live page: https://pierre-kookis.github.io/leonida-progress/**

A progress page for [Leonida](https://github.com/ItsNotRexed/Leonida), rebuilt from Leonida's docs instead of typed
by hand. One self-contained HTML file: no server, no external scripts.

## How it stays current

- **When the page opens**, it asks GitHub for Leonida's latest `main` commit. If it is newer than the snapshot in
  the page, it reads the same docs from `raw.githubusercontent.com` and applies the same rules (`rows.json`) in
  the browser. Rows that changed since the snapshot turn blue. The ↻ button reads them again. If GitHub cannot be
  reached (offline, or the API's 60 requests an hour per address), the page shows its snapshot and says so.
- **The GitHub Actions workflow** (`.github/workflows/pages.yml`) rebuilds the page from Leonida's `main` every
  6 hours, on every push here and by hand, and publishes it on GitHub Pages. That rebuild also refreshes the
  per-instruction ISA grid, which needs AMD's XML and Python, so it is the one part that does not update in the
  browser.

## What it shows

- **Boot milestones** M0–M7, read from `docs/d3d12_vulkan.md` §6.
- **Shader translator, runtime loader, assets**: each row is a rule over a file in `docs/` (see `rows.json`). Hover a row to see the file, line and sentence the number comes from; click to open that line on
  GitHub at the commit it was read from. A row whose sentence changed shows "source not found" instead of a stale value.
- **RDNA2 ISA grid**: one cell per instruction, from Leonida's `tools/isa_coverage.py` run on AMD's
  machine-readable ISA XML. Search an instruction, hide or show a class from the legend. Without the XML, the grid
  is drawn from the totals quoted in `docs/isa_coverage.md`.

Overall = average of the areas; an area = average of its rows (milestones: met 1, partly met 0.5, open 0).

## Use

Python 3.9+, standard library only.

```sh
git clone https://github.com/ItsNotRexed/Leonida
python -I progress.py --repo Leonida --out progress.html
```

Opened from disk, the page still updates itself from GitHub when the browser allows it.

For the per-instruction ISA grid, get AMD's XML (MIT licence) from
[GPUOpen](https://gpuopen.com/machine-readable-isa) and pass it:

```sh
curl -L -o isa.zip https://gpuopen.com/download/machine-readable-isa/latest/
unzip isa.zip amdgpu_isa_rdna2.xml
python -I progress.py --repo Leonida --isa amdgpu_isa_rdna2.xml --out progress.html
```

Options:

| Option | What it does |
|---|---|
| `--repo` | the Leonida checkout to read (required) |
| `--isa` | `amdgpu_isa_rdna2.xml`, for the live ISA grid |
| `--local` | a JSON file of your own measurements that replace rows: `{"rows": {"<row label>": {"n": 1, "d": 2, "note": "..."}}}`; those rows are marked ⌂ |
| `--out` | the page to write (default `progress.html`) |
| `--json` | print the extracted data instead of writing the page |

## Adding a row

Add an entry to `rows.json` with its `area`, `label` and `path`, and one rule:

- `regex`: named groups give `n` and `d` (a count out of a total), `f` and `d` (failures out of a total) or `p`
  (a percentage). Write Python syntax (`(?P<n>...)`); the page converts it for the browser.
- `table` + `match`: counts the rows of the markdown table whose header starts with `table` whose last cell is `match`.
- `absent`: 1/1 when the text is no longer in the doc, 0/1 while it is.

Run `python -I progress.py --repo Leonida --json` to check what it extracts. `progress.py` and the script in
`template.html` apply the same rules; change both together.

## No game data

The page holds only counts already published in Leonida's `docs/`. Never add game files, extracted assets,
shaders or anything derived from them to this repository, as for Leonida itself.

## Licence

GPL-3.0, as Leonida.
