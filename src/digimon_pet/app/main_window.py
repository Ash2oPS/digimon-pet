from __future__ import annotations

import copy
import random
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from digimon_pet import platform as desktop_platform
from digimon_pet.app.collection_dialog import CollectionDialog
from digimon_pet.app.debug_panel import DebugPanel
from digimon_pet.app.inventory_window import InventoryItem, InventoryWindow
from digimon_pet.app.item_manager_window import ItemManagerWindow
from digimon_pet.app.pet_widget import PetWidget
from digimon_pet.app.radial_menu import RadialPetMenu
from digimon_pet.app.sprite_runtime import SpriteAnimation, load_runtime_manifest, resolve_sprite_animation
from digimon_pet.app.stats_window import StatsWindow
from digimon_pet.app.theme import APP_QSS
from digimon_pet.app.window_positioning import offset_window_position
from digimon_pet.data import load_dw1_digivolutions, load_item_catalog, load_species
from digimon_pet.domain import battle, clean, feed, scold, sleep, train, wake
from digimon_pet.domain.care import apply_tick
from digimon_pet.domain.items import ItemEffectType, ItemType, can_use_item, choose_weighted_item, use_item
from digimon_pet.domain.lifecycle import (
    BABY_1_CHOICES,
    EvolutionSchedule,
    advance_lifecycle,
    choose_rebirth,
    force_evolve_to,
    next_lifecycle_event,
)
from digimon_pet.domain.models import GrowthStage, PetState, Species
from digimon_pet.paths import PROJECT_ROOT
from digimon_pet.storage import debug_settings
from digimon_pet.storage import load_pet_state, save_pet_state
from digimon_pet.storage import save_store

SECONDARY_EVENT_MIN_SECONDS = 240
SECONDARY_EVENT_MAX_SECONDS = 360
SECONDARY_EVENT_TTL_SECONDS = 30
SECONDARY_EVENT_KINDS = ("meat", "dumbbell")
SECONDARY_EVENT_ITEM_KIND = "item"
SECONDARY_EVENT_ITEM_CHANCE_ROLL = 1
SECONDARY_EVENT_ITEM_CHANCE_SIDES = 3
SECONDARY_EVENT_ITEM_POOL = "secondary_event"
BONUS_STATS = ("hp", "mp", "offense", "defense", "speed", "brains")
PASSIVE_GROWTH_STATS = ("hp", "mp", "offense", "defense", "speed", "brains")
NATURAL_DEATH_EVOLUTION_TARGET_ID = "bakemon"
NATURAL_DEATH_EVOLUTION_CHANCE = 0.1


def _item_has_instant_death_effect(item) -> bool:
    return any(effect.type == ItemEffectType.INSTANT_DEATH for effect in item.effects)


def _baby_choice_pixmap(species: Species, manifest: dict, discovered: bool) -> QPixmap:
    pixmap = _pixmap_for_species(species, manifest)
    if pixmap is not None:
        display = pixmap if discovered else _silhouette(pixmap)
        return display.scaled(58, 58, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
    return _unknown_baby_pixmap()


def _pixmap_for_species(species: Species, manifest: dict) -> QPixmap | None:
    state = PetState(species_id=species.id, stage=species.stage)
    animation = resolve_sprite_animation(state, species, manifest)
    if animation is None:
        return None
    path = PROJECT_ROOT / Path(animation.path)
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    frame = _first_frame_rect(pixmap, animation)
    return pixmap.copy(frame) if frame is not None else pixmap


def _first_frame_rect(pixmap: QPixmap, animation: SpriteAnimation) -> QRect | None:
    if animation.frame_count <= 1:
        return None
    frame_width = animation.frame_width or pixmap.width() // animation.frame_count
    frame_height = animation.frame_height or pixmap.height()
    if frame_width <= 0 or frame_height <= 0:
        return None
    return QRect(0, 0, frame_width, frame_height)


def _silhouette(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                image.setPixelColor(x, y, QColor(5, 5, 6, color.alpha()))
    return QPixmap.fromImage(image)


def _unknown_baby_pixmap() -> QPixmap:
    pixmap = QPixmap(58, 58)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#050506"))
    painter.drawEllipse(QRect(10, 10, 38, 38))
    painter.setPen(QColor("#ffd166"))
    painter.setFont(painter.font())
    painter.drawText(QRect(10, 8, 38, 42), Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return pixmap


class BabyChoiceDialog(QDialog):
    def __init__(
        self,
        baby_ids: Sequence[str],
        species: dict[str, Species],
        discovered_species_ids: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Baby Digimon")
        self.setStyleSheet(APP_QSS)
        self.setMinimumWidth(500)
        self._selected_baby_id = baby_ids[0] if baby_ids else ""
        self._buttons: dict[str, QToolButton] = {}
        self._manifest = load_runtime_manifest()
        discovered = set(discovered_species_ids)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Baby1:")
        title.setObjectName("Title")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, baby_id in enumerate(baby_ids):
            baby_species = species[baby_id]
            is_discovered = baby_id in discovered
            button = QToolButton(self)
            button.setObjectName("BabyChoiceCard")
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIcon(QIcon(_baby_choice_pixmap(baby_species, self._manifest, is_discovered)))
            button.setIconSize(QSize(58, 58))
            button.setText(baby_species.name if is_discovered else "???")
            button.setFixedSize(96, 108)
            button.clicked.connect(lambda checked=False, selected_id=baby_id: self._select_baby(selected_id))
            self._buttons[baby_id] = button
            grid.addWidget(button, index // 4, index % 4)
        layout.addLayout(grid)
        if self._selected_baby_id:
            self._select_baby(self._selected_baby_id)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_baby(self, baby_id: str) -> None:
        self._selected_baby_id = baby_id
        for button_id, button in self._buttons.items():
            button.setChecked(button_id == baby_id)

    def selected_baby_id(self) -> str:
        return self._selected_baby_id


class PetWindow(QWidget):
    def __init__(self, overlay: bool, debug: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._overlay = overlay
        self._debug = debug
        self._species = load_species()
        self._digivolutions = load_dw1_digivolutions()
        self._item_catalog = load_item_catalog()
        self._lifecycle_schedule = EvolutionSchedule()
        self._debug_settings = debug_settings.load_debug_settings()
        self._debug_time_scale = self._debug_settings.time_scale
        self._auto_rebirth_random = self._debug_settings.auto_rebirth_random
        self._auto_lifecycle_events = self._debug_settings.auto_lifecycle_events
        self._rng = random.Random()
        self._needs_initial_baby_choice = not save_store.SAVE_PATH.exists()
        self._state = load_pet_state()
        self._pending_lifecycle_kind: str | None = None
        self._pending_inventory_item_id: str | None = None
        self._lifecycle_animating = False
        self._lifecycle_animating_kind: str | None = None
        self._lifecycle_resolved_during_animation = False
        self._direction = QPoint(3, 0)
        self._drag_offset: QPoint | None = None
        self._was_dragging = False
        self._positioned_once = False
        self._collection_dialog: CollectionDialog | None = None
        self._stats_window: StatsWindow | None = None
        self._inventory_window: InventoryWindow | None = None
        self._item_manager_window: ItemManagerWindow | None = None
        self._radial_menu: RadialPetMenu | None = None
        self._resume_move_after_radial_menu = False
        self._secondary_event_kind: str | None = None
        self._secondary_event_ttl_seconds = 0
        self._secondary_event_seconds_remaining = self._next_secondary_event_delay()

        self._configure_window()

        self._pet_widget = PetWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pet_widget)

        self._debug_panel = DebugPanel(
            schedule_changed=self._set_lifecycle_schedule,
            time_scale_changed=self._set_debug_time_scale,
            stat_changed=self._set_pet_stat,
            auto_rebirth_changed=self._set_auto_rebirth_random,
            auto_lifecycle_changed=self._set_auto_lifecycle_events,
            reset_stats_requested=self._reset_stat_progression,
            reset_collection_requested=self._reset_collection_progression,
            item_manager_requested=self._open_item_manager,
        )
        self._debug_panel.setStyleSheet(APP_QSS)
        self._debug_panel.set_schedule_values(self._lifecycle_schedule)
        self._debug_panel._time_scale_input.setValue(self._debug_time_scale)
        self._debug_panel.set_auto_rebirth_enabled(self._auto_rebirth_random)
        self._debug_panel.set_auto_lifecycle_enabled(self._auto_lifecycle_events)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

        self._move_timer = QTimer(self)
        self._move_timer.timeout.connect(self._move_pet)

        if self._needs_initial_baby_choice:
            self._prompt_initial_baby_choice()
        else:
            self._refresh()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self._was_dragging:
            event.ignore()
            return

        self._show_radial_menu()
        event.accept()

    def _ensure_radial_menu(self) -> RadialPetMenu:
        if self._radial_menu is None:
            self._radial_menu = RadialPetMenu(
                open_stats=self._open_stats,
                open_collection=self._open_collection,
                open_inventory=self._open_inventory,
                close_app=QApplication.quit,
                closed=self._radial_menu_closed,
                parent=None,
            )
        return self._radial_menu

    def _show_radial_menu(self) -> None:
        menu = self._ensure_radial_menu()
        if menu.isVisible():
            menu.hide()
        self._resume_move_after_radial_menu = self._move_timer.isActive()
        self._move_timer.stop()
        pet_center = self.frameGeometry().center()
        screen = QGuiApplication.screenAt(pet_center)
        screen_geometry = (
            screen.availableGeometry()
            if screen is not None
            else QApplication.primaryScreen().availableGeometry()
        )
        menu.show_for_pet(self.frameGeometry(), screen_geometry)

    def _radial_menu_closed(self) -> None:
        if self._resume_move_after_radial_menu and not self._move_timer.isActive():
            self._move_timer.start()
        self._resume_move_after_radial_menu = False

    def _configure_window(self) -> None:
        self.setWindowTitle("Digimon Pet")
        self.setFixedSize(128, 128)
        if self._overlay:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            self.setAutoFillBackground(False)
            flags = (
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.NoDropShadowWindowHint
            )
            self.setWindowFlags(flags)
            self.setStyleSheet("background: transparent;")
        else:
            self.setWindowFlags(Qt.WindowType.Window)
            self.setStyleSheet(APP_QSS)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._positioned_once:
            self._move_to_bottom_right()
            self._positioned_once = True
        if self._overlay:
            self._apply_platform_overlay_styles()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._was_dragging = False
            self._move_timer.stop()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._was_dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            if (
                self._pending_lifecycle_kind is not None
                and not self._was_dragging
                and (
                    self._pet_widget.is_event_prompt_at(event.position().toPoint())
                    or self._pet_widget.is_pet_body_at(event.position().toPoint())
                )
            ):
                self._drag_offset = None
                self._confirm_pending_lifecycle()
                event.accept()
                return
            if (
                self._secondary_event_kind is not None
                and not self._was_dragging
                and self._pet_widget.is_event_prompt_at(event.position().toPoint())
            ):
                self._drag_offset = None
                self._claim_secondary_event()
                event.accept()
                return
            self._drag_offset = None
            self._was_dragging = False
            self._keep_inside_screen()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        self._update_pet_orientation()

    def _apply_platform_overlay_styles(self) -> None:
        if desktop_platform.is_windows():
            self._apply_windows_overlay_styles()
            return
        if desktop_platform.is_macos():
            self._apply_macos_overlay_styles()

    def _apply_windows_overlay_styles(self) -> None:
        import ctypes

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        gwl_style = -16
        gwl_exstyle = -20
        ws_popup = 0x80000000
        ws_visible = 0x10000000
        ws_caption = 0x00C00000
        ws_thickframe = 0x00040000
        ws_minimizebox = 0x00020000
        ws_maximizebox = 0x00010000
        ws_sysmenu = 0x00080000
        ws_ex_layered = 0x00080000
        ws_ex_toolwindow = 0x00000080
        ws_ex_topmost = 0x00000008
        hwnd_topmost = -1
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_noactivate = 0x0010
        swp_framechanged = 0x0020

        style = user32.GetWindowLongW(hwnd, gwl_style)
        style &= ~(ws_caption | ws_thickframe | ws_minimizebox | ws_maximizebox | ws_sysmenu)
        style |= ws_popup | ws_visible
        user32.SetWindowLongW(hwnd, gwl_style, style)

        exstyle = user32.GetWindowLongW(hwnd, gwl_exstyle)
        exstyle |= ws_ex_layered | ws_ex_toolwindow | ws_ex_topmost
        user32.SetWindowLongW(hwnd, gwl_exstyle, exstyle)

        user32.SetWindowPos(
            hwnd,
            hwnd_topmost,
            0,
            0,
            0,
            0,
            swp_nomove | swp_nosize | swp_noactivate | swp_framechanged,
        )

    def _apply_macos_overlay_styles(self) -> None:
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.raise_()

    def _handle_action(self, name: str) -> None:
        if self._pending_lifecycle_kind is not None or self._lifecycle_animating:
            return
        actions = {
            "feed": feed,
            "train": train,
            "battle": battle,
            "sleep": sleep,
            "wake": wake,
            "clean": clean,
            "scold": scold,
        }
        action = actions[name]
        action(self._state)
        self._queue_or_advance_lifecycle()
        self._save_and_refresh()

    def _tick(self) -> None:
        if self._pending_lifecycle_kind is None and not self._lifecycle_animating:
            previous_age_seconds = self._state.age_seconds
            apply_tick(self._state, 1, debug_multiplier=self._debug_time_scale)
            self._apply_passive_stat_growth(previous_age_seconds)
            if self._state.current_action not in {"sleep", "idle"}:
                self._state.current_action = "idle"
            self._queue_or_advance_lifecycle()
        self._tick_secondary_event()
        self._save_and_refresh()

    def _apply_passive_stat_growth(self, previous_age_seconds: int) -> None:
        previous_minutes = max(0, previous_age_seconds) // 60
        elapsed_minutes = self._state.age_seconds // 60 - previous_minutes
        for index in range(max(0, elapsed_minutes)):
            stat_name = self._rng.choice(PASSIVE_GROWTH_STATS)
            current_minute = previous_minutes + index + 1
            increment = self._passive_stat_increment(stat_name, current_minute)
            setattr(self._state, stat_name, getattr(self._state, stat_name) + increment)
        self._state.clamp()

    def _passive_stat_increment(self, stat_name: str, current_minute: int) -> int:
        increment = 10 if stat_name in {"hp", "mp"} else 1
        if self._state.stage == GrowthStage.ULTIMATE and current_minute % 3 == 0:
            return increment * 2
        return increment

    def _move_pet(self) -> None:
        if not self._overlay:
            return
        bounds = self._current_screen_bounds()
        if bounds is None:
            return
        next_pos = self.pos() + self._direction
        if next_pos.x() <= bounds.left() or next_pos.x() + self.width() >= bounds.right():
            self._direction.setX(-self._direction.x())
        if next_pos.y() < bounds.top():
            next_pos.setY(bounds.top())
        if next_pos.y() + self.height() > bounds.bottom():
            next_pos.setY(bounds.bottom() - self.height())
        self.move(self.pos() + self._direction)

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        margin = 24
        self.move(
            bounds.right() - self.width() - margin,
            bounds.bottom() - self.height() - margin,
        )

    def _keep_inside_screen(self) -> None:
        bounds = self._virtual_screen_bounds()
        if bounds is None:
            return
        x = min(max(self.x(), bounds.left()), bounds.right() - self.width())
        y = min(max(self.y(), bounds.top()), bounds.bottom() - self.height())
        self.move(x, y)

    def _current_screen_bounds(self) -> QRect | None:
        center = self.frameGeometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()

    def _update_pet_orientation(self) -> None:
        if not hasattr(self, "_pet_widget"):
            return
        center = self.frameGeometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        if screen is None:
            return
        bounds = screen.availableGeometry()
        if bounds is None:
            return
        self._pet_widget.set_flipped_x(center.x() < bounds.center().x())

    def _virtual_screen_bounds(self) -> QRect | None:
        screens = QApplication.screens()
        if not screens:
            return None

        bounds = screens[0].availableGeometry()
        for screen in screens[1:]:
            bounds = bounds.united(screen.availableGeometry())
        return bounds

    def _queue_or_advance_lifecycle(self) -> None:
        if self._state.needs_rebirth_choice or self._pending_lifecycle_kind is not None:
            return
        threshold = self._lifecycle_schedule.threshold_for(self._state.stage)
        if self._state.age_seconds < threshold:
            return
        self._state.age_seconds = threshold
        if self._auto_lifecycle_events:
            event = self._resolve_lifecycle_now(allow_natural_death_evolution=True)
            if event == self._natural_death_evolution_event():
                self._reveal_death_evolution_resolution()
            return
        kind = self._preview_lifecycle_kind()
        if kind is None:
            return
        self._pending_lifecycle_kind = kind
        self._clear_secondary_event(schedule_next=True)
        self._pet_widget.set_lifecycle_pending(kind)
        self._refresh()

    def _preview_lifecycle_kind(self) -> str | None:
        rng_state = self._rng.getstate()
        preview = copy.deepcopy(self._state)
        event = advance_lifecycle(
            preview,
            self._species,
            self._digivolutions,
            self._lifecycle_schedule,
            self._rng,
        )
        self._rng.setstate(rng_state)
        if event is None:
            return None
        if event.startswith("evolved:"):
            return "evolution"
        if event.startswith("died:"):
            return "death"
        return None

    def _confirm_pending_lifecycle(self) -> None:
        if self._pending_lifecycle_kind is None or self._lifecycle_animating:
            return
        kind = self._pending_lifecycle_kind
        self._pending_lifecycle_kind = None
        self._lifecycle_animating = True
        self._lifecycle_animating_kind = kind
        self._lifecycle_resolved_during_animation = False
        reveal = self._reveal_lifecycle_resolution if kind == "evolution" else None
        self._pet_widget.start_lifecycle_resolution(kind, self._finish_lifecycle_resolution, reveal)

    def _finish_lifecycle_resolution(self) -> None:
        kind = self._lifecycle_animating_kind
        if kind == "death_evolution":
            if not self._lifecycle_resolved_during_animation:
                self._reveal_death_evolution_resolution()
            self._lifecycle_animating = False
            self._lifecycle_animating_kind = None
            self._lifecycle_resolved_during_animation = False
            self._save_and_refresh()
            return

        event = None
        if not self._lifecycle_resolved_during_animation:
            event = self._resolve_lifecycle_now(
                clear_effect=False,
                allow_natural_death_evolution=kind == "death" and self._pending_inventory_item_id is None,
            )
        if event == self._natural_death_evolution_event():
            self._start_death_evolution_animation()
            return
        self._lifecycle_animating = False
        self._lifecycle_animating_kind = None
        self._lifecycle_resolved_during_animation = False
        self._save_and_refresh()

    def _reveal_lifecycle_resolution(self) -> None:
        self._resolve_lifecycle_now(clear_effect=False)
        self._lifecycle_resolved_during_animation = True
        self._save_and_refresh()

    def _resolve_lifecycle_now(
        self,
        *,
        clear_effect: bool = True,
        allow_natural_death_evolution: bool = False,
    ) -> str | None:
        if clear_effect:
            self._pet_widget.set_lifecycle_pending(None)
        discovered_before = set(self._state.discovered_species_ids)
        if self._pending_inventory_item_id is not None:
            event = self._resolve_pending_inventory_item()
        else:
            event = advance_lifecycle(
                self._state,
                self._species,
                self._digivolutions,
                self._lifecycle_schedule,
                self._rng,
            )
        if event is not None and event.startswith("evolved:"):
            self._trigger_new_badge_if_needed(discovered_before)
        if event == "died:choice_required":
            if allow_natural_death_evolution and self._roll_natural_death_evolution():
                return self._natural_death_evolution_event()
            if self._auto_rebirth_random:
                choose_rebirth(self._state, self._rng.choice(BABY_1_CHOICES), self._species)
                self._trigger_new_badge_if_needed(discovered_before)
                return event
            self._prompt_rebirth_choice()
        return event

    def _roll_natural_death_evolution(self) -> bool:
        if self._state.bakemon_lineage_used or self._state.bakemon_generation_cooldown > 0:
            return False
        return (
            NATURAL_DEATH_EVOLUTION_TARGET_ID in self._species
            and self._rng.random() < NATURAL_DEATH_EVOLUTION_CHANCE
        )

    def _natural_death_evolution_event(self) -> str:
        return f"death_evolution:{NATURAL_DEATH_EVOLUTION_TARGET_ID}"

    def _start_death_evolution_animation(self) -> None:
        self._lifecycle_animating = True
        self._lifecycle_animating_kind = "death_evolution"
        self._lifecycle_resolved_during_animation = False
        self._pet_widget.start_lifecycle_resolution(
            "evolution",
            self._finish_lifecycle_resolution,
            self._reveal_death_evolution_resolution,
        )

    def _reveal_death_evolution_resolution(self) -> None:
        target = self._species[NATURAL_DEATH_EVOLUTION_TARGET_ID]
        discovered_before = set(self._state.discovered_species_ids)
        force_evolve_to(self._state, target, self._rng)
        self._state.pending_rebirth_stat_bonuses = {}
        self._state.bakemon_lineage_used = True
        self._state.bakemon_generation_cooldown = 4
        self._trigger_new_badge_if_needed(discovered_before)
        self._lifecycle_resolved_during_animation = True
        self._save_and_refresh()

    def _resolve_pending_inventory_item(self) -> str | None:
        if self._pending_inventory_item_id is None:
            return None
        item_id = self._pending_inventory_item_id
        self._pending_inventory_item_id = None
        result = use_item(self._state, item_id, self._species, self._rng, self._item_catalog)
        return result.event if result.used else None

    def _advance_lifecycle(self) -> None:
        self._queue_or_advance_lifecycle()

    def _prompt_rebirth_choice(self) -> None:
        baby_id = self._prompt_baby_choice()
        if baby_id is None:
            return
        self._choose_rebirth(baby_id)

    def _prompt_initial_baby_choice(self) -> None:
        baby_id = self._prompt_baby_choice()
        if baby_id is not None:
            self._choose_rebirth(baby_id)
            return
        self._save_and_refresh()

    def _prompt_baby_choice(self) -> str | None:
        selected, accepted = self._get_baby_choice(list(BABY_1_CHOICES))
        if not accepted:
            return None
        return selected if selected in BABY_1_CHOICES else None

    def _get_baby_choice(self, baby_ids: list[str]) -> tuple[str, bool]:
        dialog = BabyChoiceDialog(baby_ids, self._species, self._state.discovered_species_ids, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.selected_baby_id(), accepted

    def _choose_rebirth(self, baby_id: str) -> None:
        discovered_before = set(self._state.discovered_species_ids)
        choose_rebirth(self._state, baby_id, self._species)
        self._trigger_new_badge_if_needed(discovered_before)
        self._save_and_refresh()

    def _trigger_new_badge_if_needed(self, discovered_before: set[str]) -> None:
        if self._state.species_id not in discovered_before:
            self._pet_widget.trigger_new_badge()

    def _tick_secondary_event(self) -> None:
        if self._pending_lifecycle_kind is not None or self._lifecycle_animating:
            if self._secondary_event_kind is not None:
                self._clear_secondary_event(schedule_next=True)
            return
        if self._secondary_event_kind is not None:
            self._secondary_event_ttl_seconds -= 1
            if self._secondary_event_ttl_seconds <= 0:
                self._clear_secondary_event(schedule_next=True)
            return
        self._secondary_event_seconds_remaining -= 1
        if self._secondary_event_seconds_remaining <= 0:
            self._show_secondary_event()

    def _show_secondary_event(self, kind: str | None = None) -> None:
        if self._pending_lifecycle_kind is not None or self._lifecycle_animating:
            return
        self._secondary_event_kind = kind or self._choose_secondary_event_kind()
        self._secondary_event_ttl_seconds = SECONDARY_EVENT_TTL_SECONDS
        self._secondary_event_seconds_remaining = 0
        self._pet_widget.set_secondary_event_prompt(self._secondary_event_kind)

    def _choose_secondary_event_kind(self) -> str:
        if self._rng.randint(1, SECONDARY_EVENT_ITEM_CHANCE_SIDES) == SECONDARY_EVENT_ITEM_CHANCE_ROLL:
            return SECONDARY_EVENT_ITEM_KIND
        return self._rng.choice(SECONDARY_EVENT_KINDS)

    def _claim_secondary_event(self) -> None:
        if self._secondary_event_kind is None:
            return
        gains: dict[str, int] = {}
        for stat_name in self._rng.sample(BONUS_STATS, 2):
            increment = self._secondary_event_stat_increment(stat_name)
            setattr(self._state, stat_name, getattr(self._state, stat_name) + increment)
            gains[stat_name] = increment
        item_gain = self._grant_secondary_event_item() if self._secondary_event_kind == SECONDARY_EVENT_ITEM_KIND else None
        self._state.clamp()
        item_gain_icon_path = self._item_catalog.items[item_gain].icon_path if item_gain is not None else None
        self._pet_widget.trigger_stat_gain_text(
            gains,
            item_gains=1 if item_gain is not None else 0,
            item_gain_icon_path=item_gain_icon_path,
        )
        self._clear_secondary_event(schedule_next=True)
        self._save_and_refresh()

    def _grant_secondary_event_item(self) -> str | None:
        item_id = choose_weighted_item(self._item_catalog, SECONDARY_EVENT_ITEM_POOL, self._rng)
        if item_id is None:
            return None
        self._state.inventory[item_id] = self._state.inventory.get(item_id, 0) + 1
        return item_id

    def _clear_secondary_event(self, *, schedule_next: bool = False) -> None:
        self._secondary_event_kind = None
        self._secondary_event_ttl_seconds = 0
        if schedule_next:
            self._secondary_event_seconds_remaining = self._next_secondary_event_delay()
        self._pet_widget.set_secondary_event_prompt(None)

    def _next_secondary_event_delay(self) -> int:
        return self._rng.randint(SECONDARY_EVENT_MIN_SECONDS, SECONDARY_EVENT_MAX_SECONDS)

    def _secondary_event_stat_increment(self, stat_name: str) -> int:
        if self._state.stage == GrowthStage.ULTIMATE:
            return 120 if stat_name in {"hp", "mp"} else 12
        return 100 if stat_name in {"hp", "mp"} else 10

    def _save_and_refresh(self) -> None:
        save_pet_state(self._state)
        self._refresh()

    def _refresh(self) -> None:
        species = self._species[self._state.species_id]
        self._pet_widget.set_pet(self._state, species)
        next_event = next_lifecycle_event(self._state, self._lifecycle_schedule)
        self._debug_panel.refresh(self._state, species, next_event)
        if self._stats_window is not None:
            self._stats_window.refresh(self._state, species)
        self._refresh_inventory_window()

    def _set_lifecycle_schedule(self, schedule: EvolutionSchedule) -> None:
        self._lifecycle_schedule = schedule
        self._refresh()

    def _set_debug_time_scale(self, time_scale: int) -> None:
        self._debug_time_scale = max(1, int(time_scale))
        self._save_debug_settings()

    def _set_auto_rebirth_random(self, enabled: bool) -> None:
        self._auto_rebirth_random = bool(enabled)
        self._save_debug_settings()

    def _set_auto_lifecycle_events(self, enabled: bool) -> None:
        self._auto_lifecycle_events = bool(enabled)
        if self._auto_lifecycle_events and self._pending_lifecycle_kind is not None:
            self._pending_lifecycle_kind = None
            self._resolve_lifecycle_now()
            self._save_and_refresh()
        self._save_debug_settings()

    def _save_debug_settings(self) -> None:
        self._debug_settings.time_scale = self._debug_time_scale
        self._debug_settings.auto_rebirth_random = self._auto_rebirth_random
        self._debug_settings.auto_lifecycle_events = self._auto_lifecycle_events
        debug_settings.save_debug_settings(self._debug_settings)

    def _set_pet_stat(self, name: str, value: int) -> None:
        if not hasattr(self._state, name):
            return
        setattr(self._state, name, int(value))
        self._state.clamp()
        self._save_and_refresh()

    def _reset_stat_progression(self) -> None:
        fresh = PetState(species_id=self._state.species_id, stage=self._state.stage)
        self._state.hp = fresh.hp
        self._state.mp = fresh.mp
        self._state.offense = fresh.offense
        self._state.defense = fresh.defense
        self._state.speed = fresh.speed
        self._state.brains = fresh.brains
        self._state.generation_stat_bonuses = {}
        self._state.pending_rebirth_stat_bonuses = {}
        self._save_and_refresh()

    def _reset_collection_progression(self) -> None:
        self._state.discovered_species_ids = [self._state.species_id]
        self._save_and_refresh()

    def _toggle_debug(self) -> None:
        self._debug_panel.setVisible(not self._debug_panel.isVisible())

    def _open_collection(self) -> None:
        self._state.mark_discovered()
        self._collection_dialog = CollectionDialog(
            self._species,
            self._state.discovered_species_ids,
            self._digivolutions,
            self,
        )
        self._position_secondary_window(self._collection_dialog)
        self._collection_dialog.show()
        self._collection_dialog.raise_()
        self._collection_dialog.activateWindow()

    def _open_stats(self) -> None:
        if self._stats_window is None:
            self._stats_window = StatsWindow(self)
        self._stats_window.refresh(self._state, self._species[self._state.species_id])
        self._position_secondary_window(self._stats_window)
        self._stats_window.show()
        self._stats_window.raise_()
        self._stats_window.activateWindow()

    def _open_inventory(self) -> None:
        if self._inventory_window is None:
            self._inventory_window = InventoryWindow(item_used=self._use_inventory_item, parent=self)
        self._refresh_inventory_window()
        self._position_secondary_window(self._inventory_window)
        self._inventory_window.show()
        self._inventory_window.raise_()
        self._inventory_window.activateWindow()

    def _open_item_manager(self) -> None:
        if not self._debug:
            return
        if self._item_manager_window is None:
            self._item_manager_window = ItemManagerWindow(
                self._item_catalog,
                self._species,
                PROJECT_ROOT,
                parent=None,
            )
        anchor = self._debug_panel if self._debug_panel.isVisible() else self
        self._position_secondary_window(self._item_manager_window, anchor)
        self._item_manager_window.show()
        self._item_manager_window.raise_()
        self._item_manager_window.activateWindow()

    def _position_secondary_window(self, window: QWidget, anchor: QWidget | None = None) -> None:
        window.adjustSize()
        window_size = window.size().expandedTo(window.minimumSize())
        anchor_geometry = (anchor or self).frameGeometry()
        screen = QGuiApplication.screenAt(anchor_geometry.center()) or QApplication.primaryScreen()
        if screen is None:
            return
        window.move(offset_window_position(anchor_geometry, window_size, screen.availableGeometry()))

    def _use_inventory_item(self, item_id: str) -> None:
        if self._pending_lifecycle_kind is not None or self._lifecycle_animating:
            return
        result = can_use_item(self._state, item_id, self._species, self._item_catalog)
        if not result.used:
            self._refresh()
            return
        definition = self._item_catalog.items.get(item_id)
        if definition is not None and definition.type == ItemType.CONSUMABLE:
            if _item_has_instant_death_effect(definition):
                self._pending_inventory_item_id = item_id
                self._pending_lifecycle_kind = "death"
                self._clear_secondary_event(schedule_next=True)
                self._pet_widget.set_lifecycle_pending("death")
                self._refresh()
                return
            result = use_item(self._state, item_id, self._species, self._rng, self._item_catalog)
            if result.used:
                if result.stat_gains:
                    self._pet_widget.trigger_stat_gain_text(result.stat_gains)
                if result.event == "died:choice_required":
                    if self._auto_rebirth_random:
                        choose_rebirth(self._state, self._rng.choice(BABY_1_CHOICES), self._species)
                    else:
                        self._prompt_rebirth_choice()
                self._save_and_refresh()
            else:
                self._refresh()
            return
        self._pending_inventory_item_id = item_id
        self._pending_lifecycle_kind = "evolution"
        self._clear_secondary_event(schedule_next=True)
        self._pet_widget.set_lifecycle_pending("evolution")
        self._refresh()

    def _refresh_inventory_window(self) -> None:
        if self._inventory_window is None:
            return
        self._inventory_window.set_items(self._inventory_items())

    def _inventory_items(self) -> list[InventoryItem]:
        items: list[InventoryItem] = []
        for item_id, quantity in self._state.inventory.items():
            definition = self._item_catalog.items.get(item_id)
            if definition is None:
                continue
            icon_path = None
            if definition.icon_path is not None:
                icon_path = str(PROJECT_ROOT / definition.icon_path)
            items.append(
                InventoryItem(
                    id=item_id,
                    name=definition.name,
                    quantity=quantity,
                    icon_path=icon_path,
                    description=definition.description,
                )
            )
        return items

    def toggle_debug(self) -> None:
        self._toggle_debug()
