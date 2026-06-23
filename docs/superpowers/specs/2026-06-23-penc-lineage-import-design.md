# PenC Lineage Import Design

## Goal

Expand the current Digimon catalog with Digimon Pendulum Color content while preserving the game's existing identity and data safety.

The import should:

- Add PenC Digimon and lineages up to Ultimate.
- Enrich existing lineages when PenC shares Digimon already present in the game.
- Add complete new Baby-to-Ultimate lineages when PenC has no overlap with existing lineages.
- Keep existing sprites for existing Digimon.
- Use PenC sprites for newly added Digimon.
- Add PenC as a sprite fetch source in the existing Digimon Manager sprite import flow.
- Generate reviewable staging output before applying any catalog changes.

## Scope

In scope:

- PenC roster extraction.
- PenC lineage extraction.
- PenC sprite discovery and import support.
- Staging files under `data/imports/penc/`.
- Proposed additions to `data/species.json` and `data/dw1_digivolutions.json`.
- Proposed sprite-source changes for newly added Digimon.
- Digimon Manager support for PenC as another fetchable sprite source.
- Validation and report generation before applying changes.

Out of scope:

- Replacing sprites for Digimon that already exist in the game.
- Rescaling existing evolution requirements.
- Adding Mega or higher stages to the runtime catalog.
- Implementing PenC-native mechanics such as effort hearts, win ratio, slots, or Jogress as gameplay systems.
- Creating separate species for alternate forms in this pass.

## Import Strategy

The import runs in two phases.

First, a staging phase extracts and normalizes PenC data into:

- `data/imports/penc/raw.json`
- `data/imports/penc/proposal.json`
- `data/imports/penc/report.md`

Second, an apply phase updates game data only after the staging report has been reviewed.

The staging phase is allowed to record Mega and alternate-form data for audit, but the proposal must not apply those entries to runtime files.

## Lineage Rules

Existing game data remains authoritative.

When a PenC lineage contains a Digimon that already exists in the game, PenC branches are added in addition to existing branches. Existing natural evolutions are not removed or replaced.

When a PenC lineage has no overlap with any existing lineage, the importer proposes the complete Baby-to-Ultimate lineage.

The runtime proposal must exclude Mega or higher targets. If excluding a Mega leaves a valid Ultimate endpoint, the lineage is kept up to that Ultimate. If a branch only becomes meaningful at Mega, it is reported but not applied.

## Alternate Forms

Alternate forms are ignored for this implementation pass.

Examples include attribute/color variants such as `Metal Greymon (Vaccine)`. If a PenC alternate form clearly maps to an existing canonical species, the importer may use the canonical species for matching. It must not create a separate runtime species for that alternate form.

Ambiguous alternate-form mappings must be listed in the report instead of applied.

## Names and Aliases

The game keeps existing canonical names and IDs.

PenC/Humulos names are added as aliases only when needed for matching or sprite resolution. Examples:

- `Biyomon` alias `Piyomon`
- `Phoenixmon` alias `Hououmon`
- `HerculesKabuterimon` alias `Herakle Kabuterimon`
- `MegaSeadramon` alias `Mega Seadramon`

New species IDs should follow the existing lowercase ID convention.

## Evolution Requirements

New evolution requirements use the game's existing stat-based condition model, not PenC-native requirements.

The new stat scale should support future caps:

- `hp` and `mp`: up to `99999`
- `offense`, `defense`, `speed`, `brains`: up to `9999`

The import should use a broad scaling band for newly added requirements:

- Rookie targets: approximately `300-1500` HP/MP and `30-150` other stats.
- Champion targets: approximately `5000-18000` HP/MP and `500-1800` other stats.
- Ultimate targets: approximately `25000-65000` HP/MP and `2500-6500` other stats.

Conditions should be assigned by Digimon profile, not random formula alone. For example:

- Aquatic Digimon should lean toward HP, MP, defense, or brains.
- Beast/agile Digimon should lean toward speed and offense.
- Machine/cyborg Digimon should lean toward defense, offense, and brains.
- Holy/mystic Digimon should lean toward MP, speed, and brains.
- Insect/plant Digimon should lean toward HP, defense, speed, or brains depending on the species.

Existing evolution requirements are not rescaled in this pass. The report should flag old branches that are much easier than newly proposed branches.

## Sprite Rules

Existing Digimon keep their current runtime sprite resolution.

For newly added Digimon, PenC sprites are imported and used as the preferred source when available.

PenC should be added as a normal sprite provider in the existing Digimon Manager fetch/import system. The manager already supports multiple sprite sources, so this work should extend that source discovery instead of creating a separate UI flow.

The Digimon Manager should be able to:

- Discover PenC sprite candidates for the selected Digimon.
- Show the candidate through the existing preview flow.
- Import the chosen PenC sprite through the existing manifest/roster/runtime manifest pipeline.

For existing Digimon, PenC should appear as a manual import option but should not be selected automatically by the mass import.

## Validation

Staging validation is blocking for:

- Broken species references.
- Invalid stage transitions.
- Runtime proposal containing Mega or higher species.
- New runtime species without a PenC sprite candidate.
- Duplicate species IDs.
- Duplicate natural evolution IDs.
- Alternate-form entries that would create ambiguous runtime species.

Warnings should include:

- Existing branches that are much easier than proposed new branches.
- PenC branches excluded because they exceed Ultimate.
- PenC species skipped because they are alternate forms.
- Sprite candidates with uncertain name matching.

## Report

The report should summarize:

- Existing Digimon used as anchors.
- Existing lineages enriched.
- New lineages proposed.
- New Digimon proposed.
- PenC species excluded because they are Mega or higher.
- Alternate forms ignored or mapped.
- New sprites proposed.
- Existing sprites intentionally preserved.
- Validation errors and warnings.

The report should be readable enough to review before applying changes.

## Application

The apply phase should only run after the staging proposal is accepted.

It should update:

- `data/species.json`
- `data/dw1_digivolutions.json`
- `data/dw1_roster.json`
- `data/sprite_sources.json`
- PenC source manifest under `assets/sprite_sources/digimon_pendulum_color/`
- `data/dw1_sprite_manifest.json`
- `data/dw1_sprite_report.md`

It should not modify existing sprite preferences for existing Digimon.

## Testing

Tests should cover:

- PenC extraction fixture parsing.
- Species matching with aliases.
- Ultimate-only filtering.
- Alternate-form skipping.
- Proposal generation for overlapping and non-overlapping lineages.
- Requirement generation staying within the new stat bands.
- No replacement of existing sprite preferences.
- PenC sprite provider discovery/import in Digimon Manager import helpers.
- Catalog validation after applying a fixture proposal.

## Rollout

1. Build staging import and report generation.
2. Add PenC sprite provider support to the existing sprite import helpers.
3. Generate the first PenC staging report.
4. Review report before applying.
5. Apply accepted proposal to game data.
6. Run focused catalog, sprite, and manager tests.
