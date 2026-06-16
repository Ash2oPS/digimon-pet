from __future__ import annotations

from digimon_pet.domain.models import PetState


def feed(state: PetState) -> PetState:
    state.hunger -= 25
    state.fatigue += 3
    state.weight += 1
    state.happiness += 1
    state.current_action = "eat"
    state.clamp()
    return state


def train(state: PetState) -> PetState:
    state.training_count += 1
    state.fatigue += 18
    state.hunger += 12
    state.discipline += 4
    stat_cycle = state.training_count % 6
    if stat_cycle == 1:
        state.hp += 200
    elif stat_cycle == 2:
        state.mp += 200
    elif stat_cycle == 3:
        state.offense += 25
    elif stat_cycle == 4:
        state.defense += 25
    elif stat_cycle == 5:
        state.speed += 25
    else:
        state.brains += 25
    state.current_action = "train"
    state.clamp()
    return state


def battle(state: PetState) -> PetState:
    state.won_battles += 1
    state.hunger += 10
    state.fatigue += 12
    state.hp += 80
    state.mp += 80
    state.offense += 10
    state.defense += 10
    state.speed += 10
    state.brains += 10
    if state.won_battles % 3 == 0:
        state.techniques_mastered += 1
    state.current_action = "train"
    state.clamp()
    return state


def sleep(state: PetState) -> PetState:
    state.is_sleeping = True
    state.current_action = "sleep"
    state.clamp()
    return state


def wake(state: PetState) -> PetState:
    state.is_sleeping = False
    state.current_action = "idle"
    state.clamp()
    return state


def clean(state: PetState) -> PetState:
    state.discipline += 2
    state.happiness += 2
    state.current_action = "happy"
    state.clamp()
    return state


def scold(state: PetState) -> PetState:
    state.discipline += 8
    state.happiness -= 4
    state.fatigue += 4
    state.current_action = "angry"
    state.clamp()
    return state


def apply_tick(state: PetState, elapsed_seconds: int, debug_multiplier: int = 1) -> PetState:
    elapsed = max(0, elapsed_seconds) * max(1, debug_multiplier)
    state.age_seconds += elapsed
    state.clamp()
    return state
