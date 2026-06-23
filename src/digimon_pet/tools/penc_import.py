from __future__ import annotations

import argparse
import json
from pathlib import Path

from digimon_pet.data.penc_import import (
    apply_penc_proposal_to_catalog,
    default_penc_paths,
    fetch_penc_html,
    generate_penc_proposal,
    parse_penc_html,
    write_penc_staging,
)
from digimon_pet.data.pendulum_sprite_import import SpriteImportOption, import_sprite_option
from digimon_pet.paths import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage or apply Digimon Pendulum Color catalog imports.")
    parser.add_argument("command", choices=("stage", "apply"))
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--html", type=Path, help="Use a local PenC HTML fixture instead of fetching Humulos.")
    parser.add_argument("--proposal", type=Path, help="Proposal path for apply. Defaults to data/imports/penc/proposal.json.")
    args = parser.parse_args()

    if args.command == "stage":
        return _stage(args.project_root, args.html)
    return _apply(args.project_root, args.proposal)


def _stage(project_root: Path, html_path: Path | None) -> int:
    html = html_path.read_text(encoding="utf-8") if html_path else fetch_penc_html()
    raw = parse_penc_html(html)
    species_rows = _read_json(project_root / "data" / "species.json")
    digivolutions = _read_json(project_root / "data" / "dw1_digivolutions.json")
    sprite_manifest_path = project_root / "data" / "dw1_sprite_manifest.json"
    sprite_manifest = _read_json(sprite_manifest_path) if sprite_manifest_path.exists() else {}
    proposal = generate_penc_proposal(raw, species_rows, digivolutions, sprite_manifest=sprite_manifest)
    paths = default_penc_paths(project_root)
    write_penc_staging(paths, raw, proposal)
    print(f"Wrote {paths.raw}")
    print(f"Wrote {paths.proposal}")
    print(f"Wrote {paths.report}")
    print(f"Errors: {len(proposal['errors'])}; warnings: {len(proposal['warnings'])}")
    return 1 if proposal["errors"] else 0


def _apply(project_root: Path, proposal_path: Path | None) -> int:
    paths = default_penc_paths(project_root)
    effective_proposal_path = proposal_path or paths.proposal
    proposal = _read_json(effective_proposal_path)
    if proposal.get("errors"):
        print("Refusing to apply PenC proposal with blocking errors.")
        for error in proposal["errors"]:
            print(f"- {error}")
        return 1

    species_path = project_root / "data" / "species.json"
    digivolutions_path = project_root / "data" / "dw1_digivolutions.json"
    species_rows = _read_json(species_path)
    digivolutions = _read_json(digivolutions_path)
    updated_species, updated_digivolutions = apply_penc_proposal_to_catalog(proposal, species_rows, digivolutions)

    for item in proposal.get("sprite_imports", []):
        option = SpriteImportOption(
            provider_id="humulos_penc",
            label=f"Humulos PenC ({item['name']})",
            detail=Path(str(item.get("sprite_url", ""))).name,
            species_id=str(item["species_id"]),
            name=str(item["name"]),
            source_url=str(item.get("source_url") or proposal.get("source") or ""),
            image_url=str(item.get("sprite_url") or ""),
            matched_name=str(item["name"]),
            source_name="Humulos PenC",
            metadata={"source_title": str(item["name"])},
        )
        result = import_sprite_option(option, project_root)
        if result is None:
            print(f"Failed to import PenC sprite for {item['species_id']}")
            return 1

    _write_json(species_path, updated_species)
    _write_json(digivolutions_path, updated_digivolutions)
    print(f"Applied {len(proposal.get('new_species', []))} species and {len(proposal.get('new_natural_evolutions', []))} evolutions.")
    return 0


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
