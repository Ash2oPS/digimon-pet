from __future__ import annotations

from digimon_pet.domain.models import PetState


def feed(state: PetState) -> PetState:
    state.hunger -= 25
    state.fatigue += 3
    state.current_action = "eat"
    state.clamp()
    return state


def train(state: PetState) -> PetState:
    state.training_count += 1
    state.fatigue += 18
    state.hunger += 12
    state.discipline += 4
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
    state.current_action = "happy"
    state.clamp()
    return state


def scold(state: PetState) -> PetState:
    state.discipline += 8
    state.fatigue += 4
    state.current_action = "angry"
    state.clamp()
    return state


def apply_tick(state: PetState, elapsed_seconds: int, debug_multiplier: int = 1) -> PetState:
    elapsed = max(0, elapsed_seconds) * max(1, debug_multiplier)
    state.age_seconds += elapsed

    if state.is_sleeping:
        state.fatigue -= max(1, elapsed // 5)
        state.hunger += max(1, elapsed // 20)
    else:
        state.hunger += max(1, elapsed // 15)
        state.fatigue += max(1, elapsed // 25)

    if state.hunger >= 100 or state.fatigue >= 100:
        state.care_mistakes += 1

    state.clamp()
    return state
