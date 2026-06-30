from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from digimon_pet.data.sprite_pipeline import normalize_name
from digimon_pet.domain.models import GrowthStage


PENC_URL = "https://humulos.com/digimon/penc/"
PENC_SOURCE_ID = "humulos_penc"
PENC_SPRITE_SOURCE_ID = "digimon_pendulum_color"
PENC_SPRITE_SOURCE_NAME = "Digimon Pendulum COLOR"
PENC_SPRITE_MANIFEST_PATH = "assets/sprite_sources/digimon_pendulum_color/manifest.json"
PENC_STAGE_ORDER = {
    GrowthStage.BABY.value: 0,
    GrowthStage.BABY_2.value: 1,
    GrowthStage.ROOKIE.value: 2,
    GrowthStage.CHAMPION.value: 3,
    GrowthStage.ULTIMATE.value: 4,
    GrowthStage.MEGA.value: 5,
}
HP_MP_STATS = {"hp", "mp"}
COMBAT_STATS = {"offense", "defense", "speed", "brains"}
VALID_RUNTIME_STAGES = {
    GrowthStage.BABY.value,
    GrowthStage.BABY_2.value,
    GrowthStage.ROOKIE.value,
    GrowthStage.CHAMPION.value,
    GrowthStage.ULTIMATE.value,
    GrowthStage.MEGA.value,
}
STAGE_BANDS = {
    GrowthStage.ROOKIE.value: {"hp_mp": (300, 1500), "combat": (30, 150)},
    GrowthStage.CHAMPION.value: {"hp_mp": (5000, 18000), "combat": (500, 1800)},
    GrowthStage.ULTIMATE.value: {"hp_mp": (25000, 65000), "combat": (2500, 6500)},
    GrowthStage.MEGA.value: {"hp_mp": (40000, 85000), "combat": (4000, 8500)},
}
HIGH_ULTIMATE_REQUIREMENT_THRESHOLDS = {"hp_mp": 40000, "combat": 4000}
HIGH_ULTIMATE_REQUIREMENT_SCALE = 0.85
PROFILE_STATS = {
    "aquatic": ("hp", "mp", "defense", "brains"),
    "beast": ("speed", "offense"),
    "machine": ("defense", "offense", "brains"),
    "holy": ("mp", "speed", "brains"),
    "insect_plant": ("hp", "defense", "speed", "brains"),
    "balanced": ("hp", "mp", "offense", "defense", "speed", "brains"),
}
PROFILE_KEYWORDS = {
    "aquatic": ("aqua", "marine", "sea", "whamon", "fish", "jelly", "shell", "coela", "ruka"),
    "beast": ("garuru", "leomon", "angora", "tail", "gato", "beast", "monochro", "tora", "wolf"),
    "machine": ("metal", "machine", "cyber", "mega", "dramon", "android", "haguru", "guardro", "tank"),
    "holy": ("ange", "holy", "saber", "mastemon", "phoenix", "houou", "tailmon"),
    "insect_plant": ("kabuteri", "kuwaga", "tento", "pal", "vegi", "plant", "flor", "mushi"),
}
STAGE_CLASS_MAP = {
    "baby": GrowthStage.BABY.value,
    "babyi": GrowthStage.BABY.value,
    "babyii": GrowthStage.BABY_2.value,
    "child": GrowthStage.ROOKIE.value,
    "adult": GrowthStage.CHAMPION.value,
    "perfect": GrowthStage.ULTIMATE.value,
    "ultimate": GrowthStage.MEGA.value,
    "superultimate": GrowthStage.MEGA.value,
}
DW1_STAGE_BY_APP_STAGE = {
    GrowthStage.BABY.value: "fresh",
    GrowthStage.BABY_2.value: "in_training",
}
CANONICAL_NAME_OVERRIDES = {
    "piyomon": "Biyomon",
}


@dataclass(frozen=True)
class PenCPaths:
    raw: Path
    proposal: Path
    report: Path


def fetch_penc_html(url: str = PENC_URL, *, timeout_seconds: float = 20.0) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_penc_html(html: str, *, source_url: str = PENC_URL) -> dict[str, Any]:
    species_by_slug = _parse_species(html, source_url)
    explicit_edges = _parse_explicit_edges(html, species_by_slug)
    inferred_edges = _parse_line_class_edges(html, species_by_slug)
    edges = _dedupe_edges([*explicit_edges, *inferred_edges])
    species = sorted(species_by_slug.values(), key=lambda item: (str(item.get("family", "")), PENC_STAGE_ORDER.get(str(item.get("stage", "")), 99), str(item.get("name", ""))))
    excluded = [item for item in species if item.get("excluded_reason")]
    return {
        "source_url": source_url,
        "species": species,
        "edges": edges,
        "excluded": excluded,
    }


def generate_penc_proposal(
    raw: dict[str, Any],
    species_rows: list[dict[str, Any]],
    digivolutions: dict[str, Any],
    *,
    sprite_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_species = {str(row.get("id", "")): row for row in species_rows}
    existing_edges = {str(row.get("id", "")) for row in digivolutions.get("natural_evolutions", []) if isinstance(row, dict)}
    existing_sprite_entries = (sprite_manifest or {}).get("entries", {}) if isinstance(sprite_manifest, dict) else {}
    runtime_species = [
        item
        for item in raw.get("species", [])
        if isinstance(item, dict) and not item.get("excluded_reason") and str(item.get("stage", "")) in VALID_RUNTIME_STAGES
    ]
    runtime_by_id = {str(item.get("id")): item for item in runtime_species}
    new_species: list[dict[str, Any]] = []
    sprite_imports: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []

    for item in runtime_species:
        species_id = str(item["id"])
        if species_id in existing_species:
            continue
        sprite_url = str(item.get("sprite_url", "")).strip()
        sprite_frame2_url = str(item.get("sprite_frame2_url", "")).strip()
        if not sprite_url:
            errors.append(f"{species_id} has no PenC sprite candidate")
        new_species.append(
            {
                "id": species_id,
                "name": str(item["name"]),
                "stage": str(item["stage"]),
                "aliases": list(item.get("aliases", [])),
                "sprite_slots": {},
            }
        )
        sprite_imports.append(
            {
                "species_id": species_id,
                "name": str(item["name"]),
                "sprite_url": sprite_url,
                "sprite_frame2_url": sprite_frame2_url,
                "source_url": str(item.get("profile_url") or raw.get("source_url") or PENC_URL),
                "source_family": str(item.get("family", "")),
                "preferred_source_id": PENC_SPRITE_SOURCE_ID,
            }
        )

    new_evolutions: list[dict[str, Any]] = []
    seen_new_edges: set[str] = set()
    for edge in raw.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id", ""))
        evolution_id = f"{source_id}__to__{target_id}"
        if evolution_id in existing_edges or evolution_id in seen_new_edges:
            continue
        source = runtime_by_id.get(source_id) or existing_species.get(source_id)
        target = runtime_by_id.get(target_id) or existing_species.get(target_id)
        if source is None or target is None:
            warnings.append(f"{evolution_id} skipped because source or target is excluded")
            continue
        target_stage = str(target.get("stage", ""))
        if target_stage not in VALID_RUNTIME_STAGES:
            errors.append(f"{evolution_id} targets invalid runtime stage: {target_stage}")
            continue
        new_evolutions.append(_natural_evolution_row(source, target, edge, chart_order=len(new_evolutions) + 1))
        seen_new_edges.add(evolution_id)

    duplicate_ids = _duplicates([str(item["id"]) for item in new_species])
    duplicate_edges = _duplicates([str(item["id"]) for item in new_evolutions])
    errors.extend(f"Duplicate proposed species id: {species_id}" for species_id in duplicate_ids)
    errors.extend(f"Duplicate proposed natural evolution id: {evolution_id}" for evolution_id in duplicate_edges)
    warnings.extend(_difficulty_warnings(digivolutions.get("natural_evolutions", []), new_evolutions))
    warnings.extend(
        f"{item.get('name')} excluded: {item.get('excluded_reason')}"
        for item in raw.get("excluded", [])
        if isinstance(item, dict)
    )
    preserved = sorted(str(species_id) for species_id in existing_sprite_entries if str(species_id) in existing_species)
    return {
        "source": raw.get("source_url", PENC_URL),
        "new_species": new_species,
        "new_natural_evolutions": new_evolutions,
        "sprite_imports": sprite_imports,
        "preserved_existing_sprite_species_ids": preserved,
        "excluded": copy.deepcopy(raw.get("excluded", [])),
        "warnings": warnings,
        "errors": errors,
    }


def render_penc_report(proposal: dict[str, Any]) -> str:
    lines = [
        "# PenC Import Report",
        "",
        f"Source: {proposal.get('source', PENC_URL)}",
        "",
        "## Summary",
        f"- New Digimon proposed: {len(proposal.get('new_species', []))}",
        f"- New natural evolutions proposed: {len(proposal.get('new_natural_evolutions', []))}",
        f"- New sprite imports proposed: {len(proposal.get('sprite_imports', []))}",
        f"- Existing sprites preserved: {len(proposal.get('preserved_existing_sprite_species_ids', []))}",
        f"- Excluded PenC entries: {len(proposal.get('excluded', []))}",
        "",
        "## Blocking Errors",
    ]
    errors = proposal.get("errors", [])
    lines.extend(f"- {error}" for error in errors) if errors else lines.append("- None")
    lines.extend(["", "## Warnings"])
    warnings = proposal.get("warnings", [])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None")
    lines.extend(["", "## New Digimon"])
    species = proposal.get("new_species", [])
    lines.extend(f"- {item['name']} (`{item['id']}`, {item['stage']})" for item in species) if species else lines.append("- None")
    lines.extend(["", "## New Evolutions"])
    evolutions = proposal.get("new_natural_evolutions", [])
    if evolutions:
        for row in evolutions:
            lines.append(f"- {row['source_name']} -> {row['target_name']}: {_requirements_summary(row)}")
    else:
        lines.append("- None")
    lines.extend(["", "## Sprite Imports"])
    sprite_imports = proposal.get("sprite_imports", [])
    if sprite_imports:
        for item in sprite_imports:
            frame2 = f" + {item['sprite_frame2_url']}" if item.get("sprite_frame2_url") else ""
            lines.append(f"- {item['name']} (`{item['species_id']}`): {item['sprite_url']}{frame2}")
    else:
        lines.append("- None")
    lines.extend(["", "## Excluded"])
    excluded = proposal.get("excluded", [])
    lines.extend(f"- {item.get('name')}: {item.get('excluded_reason')}" for item in excluded) if excluded else lines.append("- None")
    return "\n".join(lines) + "\n"


def write_penc_staging(paths: PenCPaths, raw: dict[str, Any], proposal: dict[str, Any]) -> None:
    paths.raw.parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths.raw, raw)
    _write_json(paths.proposal, proposal)
    paths.report.write_text(render_penc_report(proposal), encoding="utf-8")


def default_penc_paths(project_root: Path) -> PenCPaths:
    root = project_root / "data" / "imports" / "penc"
    return PenCPaths(raw=root / "raw.json", proposal=root / "proposal.json", report=root / "report.md")


def apply_penc_proposal_to_catalog(
    proposal: dict[str, Any],
    species_rows: list[dict[str, Any]],
    digivolutions: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if proposal.get("errors"):
        raise ValueError("Cannot apply PenC proposal with blocking errors")
    updated_species = copy.deepcopy(species_rows)
    existing_species_ids = {str(row.get("id", "")) for row in updated_species}
    for row in proposal.get("new_species", []):
        if str(row.get("id", "")) not in existing_species_ids:
            updated_species.append(copy.deepcopy(row))
            existing_species_ids.add(str(row.get("id", "")))

    updated_digivolutions = copy.deepcopy(digivolutions)
    evolutions = list(updated_digivolutions.get("natural_evolutions", []))
    existing_evolution_ids = {str(row.get("id", "")) for row in evolutions if isinstance(row, dict)}
    for row in proposal.get("new_natural_evolutions", []):
        if str(row.get("id", "")) not in existing_evolution_ids:
            evolutions.append(copy.deepcopy(row))
            existing_evolution_ids.add(str(row.get("id", "")))
    updated_digivolutions["natural_evolutions"] = evolutions
    indexes = copy.deepcopy(updated_digivolutions.get("indexes", {}))
    indexes["by_source"] = _indexes_by_source(evolutions)
    updated_digivolutions["indexes"] = indexes
    return updated_species, updated_digivolutions


def _parse_species(html: str, source_url: str) -> dict[str, dict[str, Any]]:
    species_by_slug: dict[str, dict[str, Any]] = {}
    row_matches = _row_div_matches(html)
    if row_matches:
        for index, match in enumerate(row_matches):
            end = row_matches[index + 1].start() if index + 1 < len(row_matches) else len(html)
            block = html[match.start() : end]
            item = _species_from_block(_tag_attr(match.group(0), "id"), block, html[: match.start()], source_url)
            if item is not None:
                species_by_slug[str(item["slug"])] = item
    if species_by_slug:
        return species_by_slug

    for match in re.finditer(r"<img\b[^>]*(?:data-src|src)=\"[^\"]*images/dot/penc/[^\"]+\"[^>]*>", html, flags=re.I):
        tag = match.group(0)
        title = _tag_attr(tag, "title") or _tag_attr(tag, "alt")
        image_url = _tag_attr(tag, "data-src") or _tag_attr(tag, "src")
        if not title or not image_url or "digitama" in title.casefold():
            continue
        name = _clean_title(title)
        slug = _slug_from_image_url(image_url) or species_id_from_name(name)
        species_by_slug.setdefault(
            slug,
            _species_item(slug, name, "", "", _absolute_url(source_url, image_url), source_url),
        )
    return species_by_slug


def _species_from_block(slug: str, block: str, prefix: str, source_url: str) -> dict[str, Any] | None:
    image_tag = _profile_image_tag(block) or _first_penc_image_tag(block)
    if not image_tag:
        return None
    title = _tag_attr(image_tag, "title") or _tag_attr(image_tag, "alt")
    image_url = _tag_attr(image_tag, "data-src") or _tag_attr(image_tag, "src")
    if not title or not image_url or "digitama" in title.casefold():
        return None
    name = _clean_title(title)
    stage = _stage_from_block(block) or _stage_from_prefix(prefix)
    family = _family_from_prefix(prefix)
    frame2_url = _frame2_sprite_url(block, source_url)
    return _species_item(slug, name, stage, family, _absolute_url(source_url, image_url), source_url, frame2_url=frame2_url)


def _species_item(
    slug: str,
    name: str,
    stage: str,
    family: str,
    sprite_url: str,
    source_url: str,
    *,
    frame2_url: str = "",
) -> dict[str, Any]:
    excluded_reason = ""
    if _is_alternate_form(name):
        excluded_reason = "alternate form"
    return {
        "slug": slug,
        "id": species_id_from_name(_canonical_name(name)),
        "name": _canonical_name(name),
        "aliases": _aliases_for_name(name),
        "stage": stage,
        "family": family,
        "sprite_url": sprite_url,
        "sprite_frame2_url": frame2_url,
        "profile_url": source_url,
        "excluded_reason": excluded_reason,
    }


def _parse_explicit_edges(html: str, species_by_slug: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for match in re.finditer(r'data-evolution-source="([^"]+)"\s+data-evolution-target="([^"]+)"', html, flags=re.I):
        source_slug = match.group(1)
        target_slug = match.group(2)
        edge = _edge_from_slugs(source_slug, target_slug, species_by_slug)
        if edge:
            edges.append(edge)
    return edges


def _parse_line_class_edges(html: str, species_by_slug: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    row_matches = _row_div_matches(html)
    for index, match in enumerate(row_matches):
        target_slug = _tag_attr(match.group(0), "id")
        end = row_matches[index + 1].start() if index + 1 < len(row_matches) else len(html)
        block = html[match.start() : end]
        for line_match in re.finditer(r'\b[a-z0-9]+_([a-z0-9]+)_line\b', block):
            source_slug = line_match.group(1)
            if source_slug == target_slug:
                continue
            edge = _edge_from_slugs(source_slug, target_slug, species_by_slug)
            if edge:
                edges.append(edge)
    return edges


def _edge_from_slugs(source_slug: str, target_slug: str, species_by_slug: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    source = species_by_slug.get(source_slug)
    target = species_by_slug.get(target_slug)
    if source is None or target is None:
        return None
    return {
        "source_slug": source_slug,
        "target_slug": target_slug,
        "source_id": str(source["id"]),
        "target_id": str(target["id"]),
        "family": str(target.get("family") or source.get("family") or ""),
    }


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        key = (str(edge.get("source_id", "")), str(edge.get("target_id", "")))
        if "" in key or key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped


def _row_div_matches(html: str) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for match in re.finditer(r"<div\b[^>]*>", html, flags=re.I):
        tag = match.group(0)
        if _tag_attr(tag, "id") and "row" in re.split(r"\s+", _tag_attr(tag, "class")):
            matches.append(match)
    return matches


def _natural_evolution_row(source: dict[str, Any], target: dict[str, Any], edge: dict[str, Any], *, chart_order: int) -> dict[str, Any]:
    source_id = str(source["id"])
    target_id = str(target["id"])
    target_stage = str(target.get("stage", ""))
    return {
        "id": f"{source_id}__to__{target_id}",
        "type": "natural",
        "source_species_id": source_id,
        "source_name": str(source.get("name", source_id)),
        "target_species_id": target_id,
        "target_name": str(target.get("name", target_id)),
        "target_stage": DW1_STAGE_BY_APP_STAGE.get(target_stage, target_stage),
        "chart_order": chart_order,
        "requirements": _requirements_for_target(target),
        "sources": [PENC_SOURCE_ID],
        "notes": [f"Imported from PenC family: {edge.get('family', '')}".strip()],
    }


def _requirements_for_target(target: dict[str, Any]) -> dict[str, Any]:
    stage = str(target.get("stage", ""))
    if stage in {GrowthStage.BABY.value, GrowthStage.BABY_2.value}:
        return _requirements({})
    profile = _profile_for_name(str(target.get("name", "")))
    band = STAGE_BANDS.get(stage)
    if band is None:
        return _requirements({})
    stats = _scaled_stats_for_profile(profile, band, str(target.get("id", target.get("name", ""))))
    return _requirements(stats)


def _requirements(stats: dict[str, int]) -> dict[str, Any]:
    return {
        "mode": "stats_only",
        "required_group_count": 1,
        "alternate": None,
        "available_base_group_count": 1 if stats else 0,
        "has_bonus_group": False,
        "groups": {"stats": stats} if stats else {},
    }


def _scaled_stats_for_profile(profile: str, band: dict[str, tuple[int, int]], seed: str) -> dict[str, int]:
    profile_stats = PROFILE_STATS.get(profile, PROFILE_STATS["balanced"])
    stats: dict[str, int] = {}
    for index, stat in enumerate(profile_stats[:4]):
        low, high = band["hp_mp"] if stat in HP_MP_STATS else band["combat"]
        spread = high - low
        value = low + round(spread * (0.45 + (0.12 * (index % 3))))
        value = _scaled_down_high_ultimate_requirement(value, stat, band)
        stats[stat] = _round_requirement(value, stat)
    if not stats:
        low, high = band["combat"]
        value = _scaled_down_high_ultimate_requirement((low + high) // 2, "brains", band)
        stats["brains"] = _round_requirement(value, "brains")
    return stats


def _scaled_down_high_ultimate_requirement(value: int, stat: str, band: dict[str, tuple[int, int]]) -> int:
    ultimate_band = STAGE_BANDS[GrowthStage.ULTIMATE.value]
    if band != ultimate_band:
        return value
    threshold_key = "hp_mp" if stat in HP_MP_STATS else "combat"
    threshold = HIGH_ULTIMATE_REQUIREMENT_THRESHOLDS[threshold_key]
    if value <= threshold:
        return value
    return round(value * HIGH_ULTIMATE_REQUIREMENT_SCALE)


def _round_requirement(value: int, stat: str) -> int:
    step = 500 if stat in HP_MP_STATS else 50
    return max(step, round(value / step) * step)


def _profile_for_name(name: str) -> str:
    normalized = normalize_name(name)
    for profile, keywords in PROFILE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return profile
    return "balanced"


def _difficulty_warnings(existing_rows: Any, new_rows: list[dict[str, Any]]) -> list[str]:
    existing_max = _max_requirement(existing_rows)
    new_min = min((_max_requirement([row]) for row in new_rows), default=0)
    if existing_max and new_min and existing_max * 3 < new_min:
        return [f"Existing requirements remain much lower than new PenC requirements ({existing_max} vs {new_min})."]
    return []


def _max_requirement(rows: Any) -> int:
    maximum = 0
    for row in rows if isinstance(rows, list) else []:
        groups = row.get("requirements", {}).get("groups", {}) if isinstance(row, dict) else {}
        stats = groups.get("stats", {}) if isinstance(groups, dict) else {}
        if isinstance(stats, dict):
            values = [int(value) for value in stats.values() if str(value).isdigit()]
            maximum = max(maximum, max(values, default=0))
    return maximum


def species_id_from_name(name: str) -> str:
    return normalize_name(name) or "newdigimon"


def _canonical_name(name: str) -> str:
    canonical = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    return CANONICAL_NAME_OVERRIDES.get(normalize_name(canonical), canonical)


def _aliases_for_name(name: str) -> list[str]:
    canonical = _canonical_name(name)
    aliases: list[str] = []
    if normalize_name(name) != normalize_name(canonical):
        aliases.append(name)
    return aliases


def _is_alternate_form(name: str) -> bool:
    return bool(re.search(r"\([^)]*\)", name))


def _profile_image_tag(block: str) -> str:
    match = re.search(r"<img\b[^>]*(?:data-src|src)=\"[^\"]*images/dot/penc/(?!frame2/)[^\"]+\"[^>]*>", block, flags=re.I)
    return match.group(0) if match else ""


def _first_penc_image_tag(block: str) -> str:
    match = re.search(r"<img\b[^>]*(?:data-src|src)=\"[^\"]*images/dot/penc/[^\"]+\"[^>]*>", block, flags=re.I)
    return match.group(0) if match else ""


def _frame2_sprite_url(block: str, source_url: str) -> str:
    match = re.search(r"<img\b[^>]*(?:data-src|src)=\"[^\"]*images/dot/penc/frame2/[^\"]+\"[^>]*>", block, flags=re.I)
    if not match:
        return ""
    tag = match.group(0)
    image_url = _tag_attr(tag, "data-src") or _tag_attr(tag, "src")
    return _absolute_url(source_url, image_url) if image_url else ""


def _tag_attr(tag: str, attr: str) -> str:
    match = re.search(rf'\b{re.escape(attr)}="([^"]*)"', tag, flags=re.I)
    return _html_unescape(match.group(1)).strip() if match else ""


def _clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", _html_unescape(title)).strip()


def _stage_from_block(block: str) -> str:
    match = re.search(r'data-stage="([^"]+)"', block, flags=re.I)
    if match:
        return _stage_from_data(match.group(1))
    return ""


def _stage_from_prefix(prefix: str) -> str:
    latest: tuple[int, str] | None = None
    for label in ("babyII", "baby", "child", "adult", "perfect", "ultimate", "superUltimate"):
        matches = list(
            re.finditer(
                rf'class="[^"]*\b{re.escape(label)}\b(?=[^"]*\bcolumn\b)[^"]*"',
                prefix,
                flags=re.I,
            )
        )
        if not matches:
            continue
        match = matches[-1]
        if latest is None or match.start() > latest[0]:
            latest = (match.start(), label)
    if latest is not None:
        return _stage_from_label(latest[1])
    return ""


def _stage_from_label(label: str) -> str:
    return STAGE_CLASS_MAP.get(normalize_name(label), "")


def _stage_from_data(label: str) -> str:
    value = label.strip()
    if value in VALID_RUNTIME_STAGES:
        return value
    return _stage_from_label(value)


def _family_from_prefix(prefix: str) -> str:
    tail = prefix[-5000:]
    matches = list(re.finditer(r"<h4[^>]*>(.*?)</h4>", tail, flags=re.I | re.S))
    if not matches:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _html_unescape(matches[-1].group(1)))).strip()


def _slug_from_image_url(url: str) -> str:
    stem = Path(url.split("?", 1)[0]).stem
    return stem.replace("_va", "").replace("_vi", "")


def _absolute_url(base_url: str, raw_url: str) -> str:
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    return urljoin(base_url, raw_url)


def _requirements_summary(row: dict[str, Any]) -> str:
    groups = row.get("requirements", {}).get("groups", {})
    stats = groups.get("stats", {}) if isinstance(groups, dict) else {}
    if not stats:
        return "No stat requirements"
    return ", ".join(f"{stat} {value}" for stat, value in stats.items())


def _indexes_by_source(evolutions: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_source: dict[str, list[str]] = {}
    for row in evolutions:
        source_id = str(row.get("source_species_id", "")).strip()
        evolution_id = str(row.get("id", "")).strip()
        if source_id and evolution_id:
            by_source.setdefault(source_id, []).append(evolution_id)
    return {source_id: sorted(ids) for source_id, ids in sorted(by_source.items())}


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _html_unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
        .replace("&nbsp;", " ")
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
