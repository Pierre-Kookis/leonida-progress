# leonida-progress

A progress page for [Leonida](https://github.com/ItsNotRexed/Leonida), rebuilt from a Leonida checkout instead of
typed by hand. One self-contained HTML file: no server, no external scripts.

- **Boot milestones** M0–M7, read from `docs/d3d12_vulkan.md` §6.
- **Shader translator, runtime loader, assets**: each row is a regex over a file in `docs/` (see `ROWS` in
  `progress.py`). Hover a row to see the file, line and sentence the number comes from; click to open that line on
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

Add an entry to `ROWS` in `progress.py`: the area, the label, and a `Src(path, regex)` whose named groups give
`n` and `d` (a count out of a total), `f` and `d` (failures out of a total) or `p` (a percentage). Run with `--json`
to check what it extracts.

## No game data

The page holds only counts already published in Leonida's `docs/`. Never add game files, extracted assets,
shaders or anything derived from them to this repository, as for Leonida itself.

## Licence

GPL-3.0, as Leonida.
