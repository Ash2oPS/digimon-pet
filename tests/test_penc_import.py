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
    assert species["heraklekabuterimon"]["excluded_reason"] == "stage exceeds Ultimate"
    assert species["metalgreymon"]["excluded_reason"] == "alternate form"
    assert species["tentomon"]["sprite_url"] == "https://humulos.com/digimon/images/dot/penc/tento.gif"
    assert {item["name"] for item in raw["excluded"]} == {"Herakle Kabuterimon", "Metal Greymon"}
    assert ("mochimon", "tentomon") in {
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
    evolution_ids = {item["id"] for item in proposal["new_natural_evolutions"]}
    assert "mochimon__to__tentomon" not in evolution_ids
    assert "tentomon__to__kabuterimon" in evolution_ids
    target = next(item for item in proposal["new_natural_evolutions"] if item["id"] == "tentomon__to__kabuterimon")
    stats = target["requirements"]["groups"]["stats"]
    assert all(500 <= value <= 18000 for value in stats.values())
    assert "tentomon" in proposal["preserved_existing_sprite_species_ids"]
    assert "Herakle Kabuterimon excluded: stage exceeds Ultimate" in proposal["warnings"]


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
            "excluded": [{"name": "Herakle Kabuterimon", "excluded_reason": "stage exceeds Ultimate"}],
            "warnings": [],
            "errors": [],
        }
    )

    assert "New Digimon proposed: 1" in report
    assert "Tentomon -> Kabuterimon" in report
    assert "Herakle Kabuterimon: stage exceeds Ultimate" in report


def _fixture_html():
    return """
    <div class="anchor"><div class="family"><h4 class="rdisplay">Nature Spirits</h4></div></div>
    <div class="baby column">
      <div id="bubb" class="row" data-stage="baby">
        <img data-src="//humulos.com/digimon/images/dot/penc/bubb.gif" title="Bubbmon">
      </div>
    </div>
    <div class="babyII column">
      <div id="mochi" class="row" data-stage="baby_2">
        <span class="nspc_bubb_line"></span>
        <img data-src="//humulos.com/digimon/images/dot/penc/mochi.gif" title="Mochimon">
      </div>
    </div>
    <div class="child column">
      <div id="tento" class="row" data-stage="rookie">
        <span class="nspc_mochi_line"></span>
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
