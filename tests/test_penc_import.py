import json

from digimon_pet.data.penc_import import (
    apply_penc_proposal_to_catalog,
    generate_penc_proposal,
    parse_penc_html,
    render_penc_report,
)


def test_parse_penc_html_extracts_species_edges_and_exclusions():
    raw = parse_penc_html(_fixture_html(), source_url="https://humulos.com/digimon/penc/")

    species = {item["id"]: item for item in raw["species"]}
    assert species["bubbmon"]["stage"] == "baby"
    assert species["mochimon"]["stage"] == "baby_2"
    assert species["tentomon"]["stage"] == "rookie"
    assert species["kabuterimon"]["stage"] == "champion"
    assert species["atlurkabuterimon"]["stage"] == "ultimate"
    assert species["heraklekabuterimon"]["stage"] == "mega"
    assert species["heraklekabuterimon"]["excluded_reason"] == ""
    assert species["metalgreymon"]["excluded_reason"] == "alternate form"
    assert species["tentomon"]["sprite_url"] == "https://humulos.com/digimon/images/dot/penc/tento.gif"
    assert species["tentomon"]["sprite_frame2_url"] == "https://humulos.com/digimon/images/dot/penc/frame2/tento.gif"
    assert {item["name"] for item in raw["excluded"]} == {"Metal Greymon"}
    assert ("mochimon", "tentomon") in {
        (edge["source_id"], edge["target_id"])
        for edge in raw["edges"]
    }


def test_parse_penc_html_maps_piyomon_to_biyomon_alias():
    raw = parse_penc_html(_fixture_html_with_piyomon())

    species = {item["slug"]: item for item in raw["species"]}
    assert species["piyo"]["id"] == "biyomon"
    assert species["piyo"]["name"] == "Biyomon"
    assert species["piyo"]["aliases"] == ["Piyomon"]
    assert ("pyocomon", "biyomon") in {
        (edge["source_id"], edge["target_id"])
        for edge in raw["edges"]
    }


def test_generate_penc_proposal_adds_new_branches_without_replacing_existing():
    raw = parse_penc_html(_fixture_html())
    species_rows = [
        {"id": "mochimon", "name": "Mochimon", "stage": "baby_2", "sprite_slots": {}},
        {"id": "tentomon", "name": "Tentomon", "stage": "rookie", "sprite_slots": {}},
    ]
    digivolutions = {
        "natural_evolutions": [
            {
                "id": "mochimon__to__tentomon",
                "type": "natural",
                "source_species_id": "mochimon",
                "source_name": "Mochimon",
                "target_species_id": "tentomon",
                "target_name": "Tentomon",
                "target_stage": "rookie",
                "chart_order": 1,
                "requirements": {"mode": "stats_only", "groups": {"stats": {"hp": 300}}},
                "sources": ["existing"],
            }
        ],
        "indexes": {"by_source": {"mochimon": ["mochimon__to__tentomon"]}},
    }

    proposal = generate_penc_proposal(raw, species_rows, digivolutions, sprite_manifest={"entries": {"tentomon": {}}})

    assert proposal["errors"] == []
    assert "bubbmon" in {item["id"] for item in proposal["new_species"]}
    assert "kabuterimon" in {item["id"] for item in proposal["new_species"]}
    assert "heraklekabuterimon" in {item["id"] for item in proposal["new_species"]}
    evolution_ids = {item["id"] for item in proposal["new_natural_evolutions"]}
    assert "mochimon__to__tentomon" not in evolution_ids
    assert "tentomon__to__kabuterimon" in evolution_ids
    assert "atlurkabuterimon__to__heraklekabuterimon" in evolution_ids
    target = next(item for item in proposal["new_natural_evolutions"] if item["id"] == "tentomon__to__kabuterimon")
    stats = target["requirements"]["groups"]["stats"]
    assert all(500 <= value <= 18000 for value in stats.values())
    assert "tentomon" in proposal["preserved_existing_sprite_species_ids"]
    mega = next(item for item in proposal["new_natural_evolutions"] if item["id"] == "atlurkabuterimon__to__heraklekabuterimon")
    mega_stats = mega["requirements"]["groups"]["stats"]
    assert mega["target_stage"] == "mega"
    assert all(40000 <= value <= 85000 for stat, value in mega_stats.items() if stat in {"hp", "mp"})
    assert all(4000 <= value <= 8500 for stat, value in mega_stats.items() if stat not in {"hp", "mp"})
    assert "Herakle Kabuterimon excluded: stage exceeds Ultimate" not in proposal["warnings"]


def test_generate_penc_proposal_does_not_readd_piyomon_when_biyomon_exists():
    raw = parse_penc_html(_fixture_html_with_piyomon())
    species_rows = [
        {"id": "pyocomon", "name": "Pyocomon", "stage": "baby_2", "sprite_slots": {}},
        {"id": "biyomon", "name": "Biyomon", "stage": "rookie", "aliases": ["Piyomon"], "sprite_slots": {}},
    ]
    digivolutions = {"natural_evolutions": [], "indexes": {"by_source": {}}}

    proposal = generate_penc_proposal(raw, species_rows, digivolutions)

    assert "piyomon" not in {item["id"] for item in proposal["new_species"]}
    assert "biyomon" not in {item["id"] for item in proposal["new_species"]}
    assert "pyocomon__to__biyomon" in {
        item["id"]
        for item in proposal["new_natural_evolutions"]
    }


def test_generate_penc_proposal_scales_down_only_high_ultimate_requirements():
    raw = {
        "source_url": "fixture",
        "species": [
            {"id": "source", "name": "Source", "stage": "champion", "sprite_url": "https://example.test/source.gif"},
            {"id": "targetchampion", "name": "Target Champion", "stage": "champion", "sprite_url": "https://example.test/champion.gif"},
            {"id": "targetultimate", "name": "Target Ultimate", "stage": "ultimate", "sprite_url": "https://example.test/ultimate.gif"},
        ],
        "edges": [
            {"source_id": "source", "target_id": "targetchampion", "family": "fixture"},
            {"source_id": "source", "target_id": "targetultimate", "family": "fixture"},
        ],
        "excluded": [],
    }
    proposal = generate_penc_proposal(raw, [], {"natural_evolutions": [], "indexes": {"by_source": {}}})

    champion_requirements = next(item for item in proposal["new_natural_evolutions"] if item["target_species_id"] == "targetchampion")["requirements"]["groups"]["stats"]
    ultimate_requirements = next(item for item in proposal["new_natural_evolutions"] if item["target_species_id"] == "targetultimate")["requirements"]["groups"]["stats"]

    assert all(value >= 5000 for stat, value in champion_requirements.items() if stat in {"hp", "mp"})
    assert all(value >= 500 for stat, value in champion_requirements.items() if stat not in {"hp", "mp"})
    assert ultimate_requirements == {"hp": 36500, "mp": 40500, "offense": 4450, "defense": 3650}


def test_apply_penc_proposal_merges_species_and_indexes():
    proposal = {
        "errors": [],
        "new_species": [{"id": "kabuterimon", "name": "Kabuterimon", "stage": "champion", "sprite_slots": {}}],
        "new_natural_evolutions": [
            {
                "id": "tentomon__to__kabuterimon",
                "type": "natural",
                "source_species_id": "tentomon",
                "source_name": "Tentomon",
                "target_species_id": "kabuterimon",
                "target_name": "Kabuterimon",
                "target_stage": "champion",
                "chart_order": 1,
                "requirements": {"mode": "stats_only", "groups": {"stats": {"hp": 10000}}},
                "sources": ["humulos_penc"],
            }
        ],
    }
    species_rows = [{"id": "tentomon", "name": "Tentomon", "stage": "rookie", "sprite_slots": {}}]
    digivolutions = {"natural_evolutions": [], "indexes": {"by_source": {}}}

    updated_species, updated_digivolutions = apply_penc_proposal_to_catalog(proposal, species_rows, digivolutions)

    assert [item["id"] for item in updated_species] == ["tentomon", "kabuterimon"]
    assert updated_digivolutions["indexes"]["by_source"] == {"tentomon": ["tentomon__to__kabuterimon"]}


def test_render_penc_report_is_reviewable():
    report = render_penc_report(
        {
            "source": "fixture",
            "new_species": [{"id": "kabuterimon", "name": "Kabuterimon", "stage": "champion"}],
            "new_natural_evolutions": [
                {
                    "source_name": "Tentomon",
                    "target_name": "Kabuterimon",
                    "requirements": {"groups": {"stats": {"hp": 10000}}},
                }
            ],
            "sprite_imports": [{"species_id": "kabuterimon", "name": "Kabuterimon", "sprite_url": "https://example.test/kabuteri.gif"}],
            "preserved_existing_sprite_species_ids": ["tentomon"],
            "excluded": [],
            "warnings": [],
            "errors": [],
        }
    )

    assert "New Digimon proposed: 1" in report
    assert "Tentomon -> Kabuterimon" in report
    assert "## Excluded\n- None" in report


def _fixture_html():
    return """
    <div class="anchor"><div class="family"><h4 class="rdisplay">Nature Spirits</h4></div></div>
    <div class="baby column">
      <div id="bubb" class="row" data-stage="baby">
        <img data-src="//humulos.com/digimon/images/dot/penc/frame2/bubb.gif" title="Bubbmon">
        <img data-src="//humulos.com/digimon/images/dot/penc/bubb.gif" title="Bubbmon">
      </div>
    </div>
    <div class="babyII column">
      <div id="mochi" class="row" data-stage="baby_2">
        <span class="nspc_bubb_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/frame2/mochi.gif" title="Mochimon">
        <img data-src="//humulos.com/digimon/images/dot/penc/mochi.gif" title="Mochimon">
      </div>
    </div>
    <div class="child column">
      <div id="tento" class="row" data-stage="rookie">
        <span class="nspc_mochi_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/frame2/tento.gif" title="Tentomon">
        <img data-src="//humulos.com/digimon/images/dot/penc/tento.gif" title="Tentomon">
      </div>
    </div>
    <div class="adult column">
      <div id="kabuteri" class="row" data-stage="champion">
        <span class="nspc_tento_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/kabuteri.gif" title="Kabuterimon">
      </div>
    </div>
    <div class="perfect column">
      <div id="atlurkabuteri" class="row" data-stage="ultimate">
        <span class="nspc_kabuteri_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/atlurkabuteri.gif" title="Atlur Kabuterimon">
      </div>
      <div id="metalgrey_va" class="row" data-stage="ultimate">
        <span class="nspc_kabuteri_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/metalgrey_va.gif" title="Metal Greymon (Vaccine)">
      </div>
    </div>
    <div class="ultimate column">
      <div id="heraklekabuteri" class="row" data-stage="mega">
        <span class="nspc_atlurkabuteri_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/heraklekabuteri.gif" title="Herakle Kabuterimon">
      </div>
    </div>
    <div data-evolution-source="mochi" data-evolution-target="tento"></div>
    """


def _fixture_html_with_piyomon():
    return """
    <div class="anchor"><div class="family"><h4 class="rdisplay">Wind Guardians</h4></div></div>
    <div class="babyII column">
      <div id="pyoco" class="row" data-stage="baby_2">
        <img data-src="//humulos.com/digimon/images/dot/penc/frame2/pyoco.gif" title="Pyocomon">
        <img data-src="//humulos.com/digimon/images/dot/penc/pyoco.gif" title="Pyocomon">
      </div>
    </div>
    <div class="child column">
      <div id="piyo" class="row" data-stage="rookie">
        <span class="wg_pyoco_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/frame2/piyo.gif" title="Piyomon">
        <img data-src="//humulos.com/digimon/images/dot/penc/piyo.gif" title="Piyomon">
      </div>
    </div>
    <div data-evolution-source="pyoco" data-evolution-target="piyo"></div>
    """
