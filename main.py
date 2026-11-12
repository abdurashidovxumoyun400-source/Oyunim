# Pydroid 3 - SDL2
# BLOCK MASTER 5.2

import os
import json
import random
import math
import struct
import wave

from kivy.app import App
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.properties import ListProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget

Window.clearcolor = (0.025, 0.035, 0.075, 1)

SIZE = 8
EMPTY = (0.10, 0.13, 0.23, 1)

COLORS = [
    (0.12, 0.52, 1, 1),
    (0.65, 0.25, 1, 1),
    (0.05, 0.85, 0.65, 1),
    (1, 0.55, 0.10, 1),
    (1, 0.25, 0.45, 1),
    (0.95, 0.80, 0.12, 1)
]

SHAPES = [
    [(0, 0)],
    [(0, 0), (0, 1)],
    [(0, 0), (1, 0)],
    [(0, 0), (0, 1), (0, 2)],
    [(0, 0), (1, 0), (2, 0)],
    [(0, 0), (0, 1), (1, 0), (1, 1)],
    [(0, 0), (0, 1), (1, 1)],
    [(0, 0), (1, 0), (2, 0), (2, 1)],
    [(0, 1), (1, 0), (1, 1), (1, 2)],
    [(0, 0), (1, 0), (1, 1), (2, 1)],
    [(0, 0), (0, 1), (0, 2), (0, 3)],
    [(0, 0), (1, 0), (2, 0), (3, 0)],
    [(0, 0), (0, 1), (0, 2),
     (1, 0), (1, 1), (1, 2)]
]


def make_button(text, color, font_size=17):
    return Button(
        text=text,
        font_size=font_size,
        bold=True,
        color=(1, 1, 1, 1),
        background_normal="",
        background_down="",
        background_color=color
    )


def show_message(title, message):
    content = BoxLayout(
        orientation="vertical",
        padding=dp(15),
        spacing=dp(12)
    )

    label = Label(
        text=message,
        font_size="17sp",
        halign="center",
        valign="middle"
    )

    label.bind(
        size=lambda obj, value:
        setattr(obj, "text_size", (value[0]-dp(10), None))
    )

    content.add_widget(label)

    close_btn = make_button(
        "YOPISH",
        (0.12, 0.38, 0.80, 1),
        16
    )

    close_btn.size_hint_y = 0.25
    content.add_widget(close_btn)

    popup = Popup(
        title=title,
        content=content,
        size_hint=(0.90, 0.62)
    )

    close_btn.bind(on_release=popup.dismiss)
    popup.open()


class TileButton(Button):

    tile_color = ListProperty(EMPTY)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.text = ""
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)

        with self.canvas.before:
            self.cell_color = Color(*EMPTY)
            self.rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(6)]
            )

        self.bind(
            pos=self.update_rect,
            size=self.update_rect,
            tile_color=self.update_color
        )

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def update_color(self, *args):
        self.cell_color.rgba = self.tile_color


class DragPieceButton(Button):

    def __init__(self, game, index, shape, color, **kwargs):
        super().__init__(**kwargs)

        self.game = game
        self.index = index
        self.shape = shape
        self.piece_color = color

        self.text = ""
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0.09, 0.12, 0.21, 1)

        self.preview_rects = []

        with self.canvas.after:
            self.preview_color = Color(*color)

            for _ in shape:
                self.preview_rects.append(
                    RoundedRectangle(
                        pos=(0, 0),
                        size=(0, 0),
                        radius=[dp(5)]
                    )
                )

        self.bind(
            pos=self.draw_preview,
            size=self.draw_preview
        )

    def draw_preview(self, *args):

        rows = max(r for r, c in self.shape) + 1
        cols = max(c for r, c in self.shape) + 1

        cell = min(
            (self.width-dp(24))/cols,
            (self.height-dp(24))/rows
        )

        cell = max(1, cell * 0.78)

        start_x = self.x + (self.width-cols*cell)/2
        start_y = self.y + (self.height-rows*cell)/2

        self.preview_color.rgba = self.piece_color

        for rect, (r, c) in zip(self.preview_rects, self.shape):
            rect.size = (cell*0.88, cell*0.88)
            rect.pos = (
                start_x+c*cell,
                start_y+(rows-1-r)*cell
            )

    def window_touch_pos(self, touch):
        return (
            self.parent.to_window(*touch.pos)
            if self.parent is not None
            else touch.pos
        )

    def on_touch_down(self, touch):

        if self.collide_point(*touch.pos):

            if self.game.start_drag(
                self.index,
                self.window_touch_pos(touch)
            ):
                touch.grab(self)
                return True

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):

        if touch.grab_current is self:
            self.game.move_drag(self.window_touch_pos(touch))
            return True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):

        if touch.grab_current is self:
            self.game.end_drag(self.window_touch_pos(touch))
            touch.ungrab(self)
            return True

        return super().on_touch_up(touch)


class FloatingPiece(Widget):

    def __init__(self, shape, color, cell_size, **kwargs):
        super().__init__(**kwargs)

        self.size_hint = (None, None)
        self.shape = shape
        self.cell_size = cell_size
        self.gap = dp(3)

        self.rows = max(r for r, c in shape) + 1
        self.cols = max(c for r, c in shape) + 1

        self.size = (
            self.cols*cell_size+(self.cols-1)*self.gap,
            self.rows*cell_size+(self.rows-1)*self.gap
        )

        self.rects = []

        with self.canvas:
            self.block_color = Color(*color)

            for _ in shape:
                self.rects.append(
                    RoundedRectangle(
                        size=(cell_size*0.90, cell_size*0.90),
                        radius=[dp(7)]
                    )
                )

        self.bind(pos=self.draw_piece)
        self.draw_piece()

    def draw_piece(self, *args):

        for rect, (r, c) in zip(self.rects, self.shape):
            rect.pos = (
                self.x+c*(self.cell_size+self.gap),
                self.y+(self.rows-1-r)*(self.cell_size+self.gap)
            )

    def follow(self, touch_pos):

        x = touch_pos[0] - self.width/2
        y = touch_pos[1] + dp(48)

        x = max(
            0,
            min(x, max(0, Window.width-self.width))
        )

        y = max(
            0,
            min(y, max(0, Window.height-self.height))
        )

        self.pos = (x, y)


class MenuScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(25), dp(25), dp(25), dp(20)],
            spacing=dp(12)
        )

        root.add_widget(Widget(size_hint_y=0.12))

        root.add_widget(
            Label(
                text="[b]BLOCK\nMASTER[/b]",
                markup=True,
                font_size="43sp",
                color=(0.25, 0.65, 1, 1),
                halign="center"
            )
        )

        root.add_widget(
            Label(
                text="PUZZLE CHALLENGE",
                font_size="14sp",
                color=(0.65, 0.75, 0.95, 1),
                size_hint_y=0.08
            )
        )

        root.add_widget(Widget(size_hint_y=0.05))

        self.best_label = Label(
            text="REKORD: 0",
            font_size="21sp",
            color=(1, 0.8, 0.2, 1),
            size_hint_y=0.10
        )

        root.add_widget(self.best_label)

        start_btn = make_button(
            "O'YINNI BOSHLASH",
            (0.10, 0.42, 0.90, 1),
            19
        )

        start_btn.size_hint_y = 0.13
        start_btn.bind(on_release=self.start_game)
        root.add_widget(start_btn)

        record_btn = make_button(
            "REYTING JADVALI",
            (0.20, 0.25, 0.43, 1)
        )

        record_btn.size_hint_y = 0.11
        record_btn.bind(on_release=self.show_records)
        root.add_widget(record_btn)

        theme_btn = make_button(
            "MAVZULAR (THEMES)",
            (0.20, 0.25, 0.43, 1)
        )

        theme_btn.size_hint_y = 0.11
        theme_btn.bind(on_release=self.show_themes)
        root.add_widget(theme_btn)

        settings_btn = make_button(
            "SOZLAMALAR",
            (0.20, 0.25, 0.43, 1)
        )

        settings_btn.size_hint_y = 0.11
        settings_btn.bind(on_release=self.show_settings)
        root.add_widget(settings_btn)

        about_btn = make_button(
            "O'YIN HAQIDA",
            (0.20, 0.25, 0.43, 1)
        )

        about_btn.size_hint_y = 0.11
        about_btn.bind(on_release=self.show_about)
        root.add_widget(about_btn)

        root.add_widget(Widget(size_hint_y=0.10))

        root.add_widget(
            Label(
                text="BLOCK MASTER 5.2",
                font_size="12sp",
                color=(0.40, 0.50, 0.70, 1),
                size_hint_y=0.06
            )
        )

        self.add_widget(root)

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        self.best_label.text = "REKORD: " + str(app.best)

    def start_game(self, instance):
        App.get_running_app().start_game()

    def show_records(self, instance):

        app = App.get_running_app()
        scores = app.all_scores

        lines = ["TOP 10 O'YINCHILAR", ""]

        if scores:

            for i, value in enumerate(scores[:10], 1):
                lines.append(f"{i}-o'rin   {value} BALL")

        else:

            lines.append(
                "Hozircha natijalar yo'q.\n"
                "Birinchi bo'lib rekord o'rnating!"
            )

        show_message(
            "REYTING JADVALI",
            "\n".join(lines)
        )

    def show_themes(self, instance):

        app = App.get_running_app()

        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(9)
        )

        content.add_widget(
            Label(
                text="O'ZINGIZGA YOQQAN DIZAYNNI TANLANG",
                font_size="14sp",
                size_hint_y=0.22
            )
        )

        popup = Popup(
            title="MAVZULAR",
            content=content,
            size_hint=(0.88, 0.58)
        )

        for theme_name, theme in app.themes.items():

            label = theme["label"] + (
                "  ✓"
                if app.current_theme == theme_name
                else ""
            )

            btn = make_button(
                label,
                theme["button"],
                16
            )

            content.add_widget(btn)

            btn.bind(
                on_release=lambda _btn, name=theme_name, p=popup:
                (app.apply_theme(name), p.dismiss())
            )

        close_btn = make_button(
            "YOPISH",
            (0.22, 0.25, 0.38, 1),
            14
        )

        content.add_widget(close_btn)
        close_btn.bind(on_release=popup.dismiss)

        popup.open()

    def show_settings(self, instance):

        show_message(
            "SOZLAMALAR",
            "Maydon: 8 x 8\n"
            "Boshqaruv: barmoq bilan sudrash\n"
            "Har safar: 3 ta blok\n"
            "Bloklar ustma-ust tushmaydi."
        )

    def show_about(self, instance):

        show_message(
            "O'YIN HAQIDA",
            "BLOCK MASTER 5.2\n\n"
            "Rangli bloklarni maydonga joylashtiring.\n"
            "To'liq qator yoki ustunni tozalang.\n"
            "Ketma-ket tozalashlar COMBO beradi!"
        )


class GameScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.score = 0
        self.selected = None
        self.dragging = False
        self.drag_target = None
        self.floating_piece = None
        self.game_over = False
        self.paused = False
        self.popup_open = False
        self.clearing = False
        self.combo_streak = 0

        self.pieces = []
        self.piece_buttons = []

        self.board = [
            [None for _ in range(SIZE)]
            for _ in range(SIZE)
        ]

        root = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(7)
        )

        header = BoxLayout(
            size_hint_y=0.09,
            spacing=dp(5)
        )

        header.add_widget(
            Label(
                text="[b]BLOCK MASTER[/b]",
                markup=True,
                font_size="25sp",
                color=(0.30, 0.65, 1, 1)
            )
        )

        self.sound_btn = make_button(
            "SOUND ON",
            (0.10, 0.38, 0.55, 1),
            10
        )

        self.sound_btn.size_hint_x = 0.22
        self.sound_btn.bind(on_release=self.toggle_sound)
        header.add_widget(self.sound_btn)

        menu_btn = make_button(
            "MENU",
            (0.17, 0.22, 0.36, 1),
            13
        )

        menu_btn.size_hint_x = 0.22
        menu_btn.bind(on_release=self.back_to_menu)
        header.add_widget(menu_btn)

        pause_btn = make_button(
            "PAUSE",
            (0.17, 0.22, 0.36, 1),
            13
        )

        pause_btn.size_hint_x = 0.22
        pause_btn.bind(on_release=self.pause_game)
        header.add_widget(pause_btn)

        root.add_widget(header)

        root.add_widget(
            Label(
                text="PUZZLE CHALLENGE - VERSION 5.2",
                font_size="11sp",
                color=(0.55, 0.65, 0.85, 1),
                size_hint_y=0.04
            )
        )

        scores = BoxLayout(
            size_hint_y=0.085,
            spacing=dp(10)
        )

        self.score_label = Label(
            text="BALL\n0",
            font_size="20sp"
        )

        self.best_label = Label(
            text="REKORD\n0",
            font_size="20sp",
            color=(1, 0.8, 0.2, 1)
        )

        scores.add_widget(self.score_label)
        scores.add_widget(self.best_label)

        root.add_widget(scores)

        self.combo_label = Label(
            text="COMBO: 0",
            font_size="15sp",
            bold=True,
            color=(0.65, 0.75, 0.95, 1),
            size_hint_y=0.045
        )

        root.add_widget(self.combo_label)

        self.status = Label(
            text="BLOKNI USHLAB SUDRANG",
            font_size="13sp",
            color=(0.25, 0.85, 0.75, 1),
            size_hint_y=0.045
        )

        root.add_widget(self.status)

        self.grid = GridLayout(
            cols=SIZE,
            spacing=dp(3),
            padding=dp(3),
            size_hint_y=0.59
        )

        self.cells = []

        for r in range(SIZE):

            row = []

            for c in range(SIZE):

                cell = TileButton(
                    tile_color=list(EMPTY)
                )

                self.grid.add_widget(cell)
                row.append(cell)

            self.cells.append(row)

        root.add_widget(self.grid)

        root.add_widget(
            Label(
                text="BLOKLARNI SUDRANG",
                font_size="15sp",
                color=(0.8, 0.85, 1, 1),
                size_hint_y=0.055
            )
        )

        self.pieces_box = BoxLayout(
            spacing=dp(8),
            size_hint_y=0.17
        )

        root.add_widget(self.pieces_box)

        restart = make_button(
            "YANGI O'YIN",
            (0.12, 0.38, 0.85, 1),
            18
        )

        restart.size_hint_y = 0.09
        restart.bind(on_release=self.restart)
        root.add_widget(restart)

        self.add_widget(root)

    def toggle_sound(self, instance):

        app = App.get_running_app()
        app.sound_enabled = not app.sound_enabled

        self.sound_btn.text = (
            "SOUND ON"
            if app.sound_enabled
            else "SOUND OFF"
        )

        self.sound_btn.background_color = (
            (0.10, 0.38, 0.55, 1)
            if app.sound_enabled
            else (0.30, 0.30, 0.34, 1)
        )

        if app.sound_enabled:
            app.play_sound("tap")

    def new_game(self):

        self.score = 0
        self.selected = None
        self.dragging = False
        self.drag_target = None

        self.remove_floating_piece()

        self.game_over = False
        self.paused = False
        self.popup_open = False
        self.clearing = False

        self.combo_streak = 0

        self.combo_label.text = "COMBO: 0"
        self.combo_label.color = (0.65, 0.75, 0.95, 1)

        for row in self.cells:
            for cell in row:
                cell.opacity = 1

        self.board = [
            [None for _ in range(SIZE)]
            for _ in range(SIZE)
        ]

        self.generate_pieces()
        self.update_score()
        self.refresh_board()

        self.status.text = "YANGI O'YIN BOSHLANDI!"

    def generate_pieces(self):

        self.pieces_box.clear_widgets()
        self.pieces = []
        self.piece_buttons = []

        for i in range(3):

            shape = random.choice(SHAPES)
            color = random.choice(COLORS)

            self.pieces.append({
                "shape": shape,
                "color": color,
                "used": False
            })

            btn = DragPieceButton(
                self,
                i,
                shape,
                color
            )

            self.piece_buttons.append(btn)
            self.pieces_box.add_widget(btn)

    def remove_used_piece(self, index):

        if 0 <= index < len(self.piece_buttons):

            btn = self.piece_buttons[index]

            if btn.parent is self.pieces_box:
                self.pieces_box.remove_widget(btn)

    def start_drag(self, index, window_pos):

        if (
            self.game_over
            or self.paused
            or self.dragging
            or self.clearing
        ):
            return False

        if (
            index < 0
            or index >= len(self.pieces)
            or self.pieces[index]["used"]
        ):
            return False

        self.selected = index

        App.get_running_app().play_sound("pick")

        self.dragging = True
        self.drag_target = None

        cell_size = max(
            dp(12),
            min(
                self.cells[0][0].width,
                self.cells[0][0].height
            )
        )

        self.floating_piece = FloatingPiece(
            self.pieces[index]["shape"],
            self.pieces[index]["color"],
            cell_size
        )

        Window.add_widget(self.floating_piece)

        self.floating_piece.follow(window_pos)
        self.status.text = "BLOKNI MAYDONGA SUDRANG"

        self.move_drag(window_pos)

        return True

    def remove_floating_piece(self):

        if self.floating_piece is not None:

            floating = self.floating_piece
            self.floating_piece = None

            if floating.parent is not None:
                floating.parent.remove_widget(floating)

    def find_cell(self, window_pos):

        grid_pos = self.grid.to_widget(*window_pos)

        for r in range(SIZE):

            for c in range(SIZE):

                if self.cells[r][c].collide_point(*grid_pos):
                    return r, c

        return None

    def get_safe_anchor(self, window_pos, shape):

        cell = self.find_cell(window_pos)

        if cell is None:
            return None

        r, c = cell

        max_r = max(x for x, y in shape)
        max_c = max(y for x, y in shape)

        return (
            max(0, min(r, SIZE-1-max_r)),
            max(0, min(c, SIZE-1-max_c))
        )

    def move_drag(self, window_pos):

        if not self.dragging or self.selected is None:
            return

        if self.floating_piece is not None:

            self.floating_piece.follow(window_pos)

            floating = self.floating_piece

            visual_anchor = (
                floating.x+floating.cell_size/2,
                floating.y+floating.height-floating.cell_size/2
            )

        else:

            visual_anchor = window_pos

        candidate = self.get_safe_anchor(
            visual_anchor,
            self.pieces[self.selected]["shape"]
        )

        if candidate is not None:

            if self.can_place(
                self.pieces[self.selected]["shape"],
                *candidate
            ):

                self.drag_target = candidate
                self.status.text = "JOYLASH MUMKIN!"

            else:

                self.drag_target = None
                self.status.text = "BO'SH JOYGA OLIB BORING"

        else:

            self.drag_target = None
            self.status.text = "BO'SH JOYGA OLIB BORING"

        self.refresh_board()

    def end_drag(self, window_pos):

        if not self.dragging:
            return

        target = self.drag_target
        selected = self.selected

        self.dragging = False
        self.remove_floating_piece()

        if target is not None and selected is not None:

            r, c = target
            shape = self.pieces[selected]["shape"]

            if self.can_place(shape, r, c):

                self.place_block(r, c, selected)

            else:

                self.status.text = "BU JOY BAND!"

        else:

            self.status.text = "BO'SH JOYGA OLIB BORING"

        self.selected = None
        self.drag_target = None

        self.refresh_board()

    def can_place(self, shape, r, c):

        for x, y in shape:

            nr = r+x
            nc = c+y

            if (
                not (0 <= nr < SIZE and 0 <= nc < SIZE)
                or self.board[nr][nc] is not None
            ):
                return False

        return True

    def place_block(self, r, c, index):

        if (
            index < 0
            or index >= len(self.pieces)
            or self.pieces[index]["used"]
        ):
            return

        piece = self.pieces[index]

        shape = piece["shape"]
        color = piece["color"]

        if not self.can_place(shape, r, c):

            self.status.text = "BU JOY BAND!"
            App.get_running_app().play_sound("error")
            return

        App.get_running_app().play_sound("place")

        for x, y in shape:
            self.board[r+x][c+y] = color

        piece["used"] = True
        self.remove_used_piece(index)

        self.score += len(shape)*10

        rows, cols = self.find_full_lines()

        if rows or cols:

            self.animate_clear_lines(rows, cols)

        else:

            self.combo_streak = 0

            self.combo_label.text = (
                "COMBO: 0  (QATOR TOZALANMADI)"
            )

            self.combo_label.color = (
                0.65, 0.75, 0.95, 1
            )

            self.update_score()
            self.refresh_board()
            self.finish_placement()

    def find_full_lines(self):

        rows = [
            r for r in range(SIZE)
            if all(
                self.board[r][c] is not None
                for c in range(SIZE)
            )
        ]

        cols = [
            c for c in range(SIZE)
            if all(
                self.board[r][c] is not None
                for r in range(SIZE)
            )
        ]

        return rows, cols

    def animate_clear_lines(self, rows, cols):

        self.clearing = True
        self.status.text = "QATOR TOZALANMOQDA!"

        App.get_running_app().play_sound("clear")

        cells_to_animate = {
            (r, c)
            for r in rows
            for c in range(SIZE)
        }

        cells_to_animate.update(
            (r, c)
            for c in cols
            for r in range(SIZE)
        )

        last_animation = None

        for r, c in cells_to_animate:

            cell = self.cells[r][c]

            Animation.cancel_all(cell)
            cell.opacity = 1

            anim = (
                Animation(opacity=0.22, duration=0.10)
                + Animation(opacity=1, duration=0.10)
                + Animation(opacity=0.22, duration=0.10)
                + Animation(opacity=0.0, duration=0.16)
            )

            anim.start(cell)
            last_animation = anim

        if last_animation is not None:

            last_animation.bind(
                on_complete=lambda animation, widget:
                self.finish_line_clear(rows, cols)
            )

        else:

            self.finish_line_clear(rows, cols)

    def finish_line_clear(self, rows, cols):

        for r in rows:
            self.board[r] = [None]*SIZE

        for c in cols:

            for r in range(SIZE):
                self.board[r][c] = None

        count = len(rows)+len(cols)

        self.combo_streak += 1

        base_bonus = (
            count*100
            + (count*50 if count >= 2 else 0)
        )

        combo_bonus = (
            self.combo_streak * 50
            if self.combo_streak >= 2
            else 0
        )

        bonus = base_bonus + combo_bonus

        self.score += bonus

        for row in self.cells:

            for cell in row:
                cell.opacity = 1

        self.clearing = False

        if self.combo_streak == 1:

            self.combo_label.text = (
                "✨ COMBO x1  |  BIRINCHI TOZALASH!"
            )

            self.combo_label.color = (
                0.35, 0.95, 0.80, 1
            )

        else:

            self.combo_label.text = (
                f"🔥 COMBO x{self.combo_streak}"
                f"  |  +{combo_bonus} BONUS!"
            )

            self.combo_label.color = (
                1, 0.72, 0.16, 1
            )

            Animation.cancel_all(self.combo_label)

            (
                Animation(font_size=dp(21), duration=0.12)
                + Animation(font_size=dp(15), duration=0.18)
            ).start(self.combo_label)

        if self.combo_streak >= 2:

            self.status.text = (
                f"COMBO x{self.combo_streak}! +{bonus} BALL"
            )

            self.status.color = (
                1, 0.78, 0.20, 1
            )

        else:

            self.status.text = (
                f"QATOR TOZALAND! +{bonus} BALL"
            )

            self.status.color = (
                0.25, 0.85, 0.75, 1
            )

        self.update_score()
        self.refresh_board()
        self.finish_placement()

    def finish_placement(self):

        if all(p["used"] for p in self.pieces):

            self.generate_pieces()
            self.status.text = "YANGI 3 TA BLOK!"

        self.check_game_over()

    def update_score(self):

        app = App.get_running_app()

        if self.score > app.best:

            app.best = self.score
            app.save_record()

        self.score_label.text = f"BALL\n{self.score}"
        self.best_label.text = f"REKORD\n{app.best}"

        Animation.cancel_all(self.score_label)

        (
            Animation(font_size=dp(25), duration=0.12)
            + Animation(font_size=dp(20), duration=0.12)
        ).start(self.score_label)

    def refresh_board(self):

        for r in range(SIZE):

            for c in range(SIZE):

                color = (
                    self.board[r][c]
                    if self.board[r][c] is not None
                    else EMPTY
                )

                self.cells[r][c].tile_color = list(color)

        if (
            not self.dragging
            or self.drag_target is None
            or self.selected is None
        ):
            return

        r, c = self.drag_target
        piece = self.pieces[self.selected]

        ghost = [
            piece["color"][0],
            piece["color"][1],
            piece["color"][2],
            0.48
        ]

        for x, y in piece["shape"]:

            nr = r+x
            nc = c+y

            if (
                0 <= nr < SIZE
                and 0 <= nc < SIZE
                and self.board[nr][nc] is None
            ):

                self.cells[nr][nc].tile_color = list(ghost)

    def pause_game(self, instance):

        if self.game_over or self.popup_open:
            return

        self.paused = True
        self.popup_open = True

        content = BoxLayout(
            orientation="vertical",
            padding=dp(15),
            spacing=dp(12)
        )

        content.add_widget(
            Label(
                text="O'YIN PAUZADA",
                font_size="22sp"
            )
        )

        resume = make_button(
            "DAVOM ETISH",
            (0.10, 0.45, 0.85, 1)
        )

        menu = make_button(
            "BOSH MENYU",
            (0.25, 0.30, 0.45, 1)
        )

        content.add_widget(resume)
        content.add_widget(menu)

        popup = Popup(
            title="BLOCK MASTER",
            content=content,
            size_hint=(0.85, 0.45),
            auto_dismiss=False
        )

        def continue_game(instance):

            self.paused = False
            self.popup_open = False
            popup.dismiss()

        def go_menu(instance):

            self.paused = False
            self.popup_open = False

            popup.dismiss()
            self.back_to_menu(None)

        resume.bind(on_release=continue_game)
        menu.bind(on_release=go_menu)

        popup.open()

    def check_game_over(self):

        for piece in self.pieces:

            if piece["used"]:
                continue

            for r in range(SIZE):

                for c in range(SIZE):

                    if self.can_place(
                        piece["shape"],
                        r,
                        c
                    ):
                        return

        self.show_game_over()

    def show_game_over(self):

        if self.popup_open:
            return

        self.game_over = True
        self.popup_open = True

        app = App.get_running_app()

        app.record_score(self.score)

        app.play_sound("gameover")

        content = BoxLayout(
            orientation="vertical",
            padding=dp(15),
            spacing=dp(12)
        )

        content.add_widget(
            Label(
                text=(
                    f"O'YIN TUGADI!\n\n"
                    f"BALL: {self.score}\n"
                    f"REKORD: {app.best}"
                ),
                font_size="21sp"
            )
        )

        again_btn = make_button(
            "QAYTA O'YNASH",
            (0.10, 0.45, 0.85, 1)
        )

        menu_btn = make_button(
            "BOSH MENYU",
            (0.25, 0.30, 0.45, 1)
        )

        content.add_widget(again_btn)
        content.add_widget(menu_btn)

        popup = Popup(
            title="BLOCK MASTER",
            content=content,
            size_hint=(0.85, 0.55),
            auto_dismiss=False
        )

        def again(instance):

            popup.dismiss()
            self.popup_open = False
            self.new_game()

        def go_menu(instance):

            popup.dismiss()
            self.popup_open = False
            self.back_to_menu(None)

        again_btn.bind(on_release=again)
        menu_btn.bind(on_release=go_menu)

        popup.open()

    def restart(self, instance):
        self.new_game()

    def back_to_menu(self, instance):

        self.dragging = False
        self.selected = None
        self.drag_target = None

        self.remove_floating_piece()

        App.get_running_app().show_menu()


class BlockMasterApp(App):

    def build(self):

        self.title = "BLOCK MASTER"

        self.best = 0
        self.all_scores = []
        self.personal_best = None

        self.sound_enabled = True
        self.sounds = {}

        self.themes = {

            "midnight": {
                "label": "MIDNIGHT BLUE",
                "background": (0.025, 0.035, 0.075, 1),
                "empty": (0.10, 0.13, 0.23, 1),
                "button": (0.10, 0.35, 0.68, 1)
            },

            "ocean": {
                "label": "OCEAN",
                "background": (0.015, 0.075, 0.095, 1),
                "empty": (0.055, 0.19, 0.22, 1),
                "button": (0.04, 0.48, 0.48, 1)
            },

            "sunset": {
                "label": "SUNSET",
                "background": (0.10, 0.035, 0.075, 1),
                "empty": (0.24, 0.10, 0.18, 1),
                "button": (0.68, 0.25, 0.28, 1)
            }
        }

        self.current_theme = "midnight"

        self.create_sound_effects()
        self.load_record()
        self.load_extra_data()

        self.manager = ScreenManager()

        self.menu_screen = MenuScreen(name="menu")
        self.game_screen = GameScreen(name="game")

        self.manager.add_widget(self.menu_screen)
        self.manager.add_widget(self.game_screen)

        self.apply_theme(self.current_theme)

        self.manager.current = "menu"

        return self.manager

    def load_extra_data(self):

        path = os.path.join(
            self.user_data_dir,
            "game_data.json"
        )

        try:

            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)

            old_scores = data.get(
                "all_scores",
                data.get("top_scores", [])
            )

            self.all_scores = sorted(
                [
                    int(v)
                    for v in old_scores
                    if int(v) >= 0
                ],
                reverse=True
            )[:1000]

            self.personal_best = (
                max(self.all_scores)
                if self.all_scores
                else None
            )

            saved_theme = data.get(
                "theme",
                "midnight"
            )

            if saved_theme in self.themes:
                self.current_theme = saved_theme

        except Exception:

            self.all_scores = []
            self.personal_best = None
            self.current_theme = "midnight"

    def save_extra_data(self):

        path = os.path.join(
            self.user_data_dir,
            "game_data.json"
        )

        try:

            with open(path, "w", encoding="utf-8") as file:

                json.dump(
                    {
                        "all_scores": self.all_scores[:1000],
                        "top_scores": self.all_scores[:10],
                        "theme": self.current_theme
                    },
                    file
                )

        except Exception as error:

            print("Save game data:", error)

    def get_rank(self, score):

        if score is None:
            return None

        return 1 + sum(
            1
            for value in self.all_scores
            if value > int(score)
        )

    def record_score(self, score):

        try:

            score = int(score)

            self.all_scores.append(score)

            self.all_scores = sorted(
                self.all_scores,
                reverse=True
            )[:1000]

            self.personal_best = max(
                score,
                self.personal_best
                if self.personal_best is not None
                else score
            )

            self.save_extra_data()

            return self.get_rank(score)

        except Exception as error:

            print("Record score:", error)
            return 1

    def apply_theme(self, name):

        global EMPTY

        if name not in self.themes:
            return

        self.current_theme = name

        theme = self.themes[name]

        Window.clearcolor = theme["background"]
        EMPTY = theme["empty"]

        self.save_extra_data()

        if hasattr(self, "game_screen"):
            self.game_screen.refresh_board()

    def create_sound_effects(self):

        try:

            os.makedirs(
                self.user_data_dir,
                exist_ok=True
            )

            effects = {

                "tap": ([660], 0.07),

                "pick": ([520, 720], 0.11),

                "place": ([440, 660], 0.13),

                "clear": (
                    [520, 660, 880, 1040],
                    0.34
                ),

                "error": ([220, 165], 0.18),

                "gameover": (
                    [440, 330, 220],
                    0.42
                )
            }

            sample_rate = 22050

            for name, (notes, duration) in effects.items():

                path = os.path.join(
                    self.user_data_dir,
                    name+".wav"
                )

                if not os.path.exists(path):

                    frames = []

                    note_duration = duration/len(notes)

                    for frequency in notes:

                        count = int(
                            sample_rate*note_duration
                        )

                        for i in range(count):

                            t = i/sample_rate

                            fade_in = min(
                                1.0,
                                i/max(
                                    1,
                                    int(sample_rate*0.008)
                                )
                            )

                            fade_out = min(
                                1.0,
                                (count-i)/max(
                                    1,
                                    int(sample_rate*0.035)
                                )
                            )

                            sample = int(
                                10500
                                * min(fade_in, fade_out)
                                * math.sin(
                                    2*math.pi*frequency*t
                                )
                            )

                            frames.append(
                                struct.pack("<h", sample)
                            )

                    with wave.open(path, "wb") as wav:

                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(sample_rate)

                        wav.writeframes(
                            b"".join(frames)
                        )

                sound = SoundLoader.load(path)

                if sound:

                    sound.volume = 0.55
                    self.sounds[name] = sound

        except Exception as error:

            print("Sound setup:", error)

    def play_sound(self, name):

        if not self.sound_enabled:
            return

        sound = self.sounds.get(name)

        if sound is not None:

            try:

                sound.stop()
                sound.play()

            except Exception as error:

                print("Sound playback:", error)

    def load_record(self):

        path = os.path.join(
            self.user_data_dir,
            "record.json"
        )

        try:

            with open(path, "r") as f:
                self.best = json.load(f).get("best", 0)

        except Exception:

            self.best = 0

    def save_record(self):

        path = os.path.join(
            self.user_data_dir,
            "record.json"
        )

        try:

            with open(path, "w") as f:
                json.dump(
                    {"best": self.best},
                    f
                )

        except Exception:
            pass

    def start_game(self):

        self.game_screen.new_game()
        self.manager.current = "game"

    def show_menu(self):

        self.manager.current = "menu"


if __name__ == "__main__":
    BlockMasterApp().run()
