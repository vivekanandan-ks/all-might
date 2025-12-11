import flet as ft
from state import state
from controls import *
import controls as controls_mod # Alias to avoid conflict if any, but explicit import is needed
from constants import *
from collections import Counter
import shlex
import subprocess
import time
import datetime
import re
from utils import get_mastodon_quote, get_mastodon_feed, fetch_opengraph_data

class SettingsScrollColumn(ft.Column):
    def did_mount(self):
        if state.last_settings_scroll > 0:
            try:
                self.scroll_to(offset=state.last_settings_scroll, duration=0)
            except Exception as e:
                print(f"Scroll restore failed: {e}")

def get_search_view(perform_search, channel_dropdown, search_field, search_icon_btn, results_column, result_count_text, filter_badge_container, toggle_filter_menu, refresh_callback=None):
    # channel_dropdown is now a GlassContainer pre-styled in main.py
    
    header_controls = [
        channel_dropdown,
        GlassContainer(
            content=ft.Row([search_field, search_icon_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=0),
            opacity=0.1,
            blur_sigma=15,
            border_radius=state.get_radius('search'),
            padding=ft.padding.only(left=15, right=5),
            expand=True
        ),
        ft.Container(content=ft.Stack([ft.IconButton(ft.Icons.FILTER_LIST, on_click=lambda e: toggle_filter_menu(True)), filter_badge_container]))
    ]
    
    if refresh_callback and state.show_refresh_button:
        header_controls.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Installed Status", on_click=refresh_callback))

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                ft.Row(controls=header_controls),
                result_count_text,
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            results_column,
                            ft.Container(height=100) # Spacer for bottom nav
                        ]
                    )
                )
            ]
        )
    )

def get_cart_view(refresh_cart_view, cart_header, cart_list):
    refresh_cart_view()
    # Refresh button for cart is handled in main.py (cart_header construction)
    return ft.Container(
        expand=True,
        padding=20,
        content=ft.Column(
            controls=[
                cart_header, 
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            cart_list,
                            ft.Container(height=100) # Spacer for bottom nav
                        ]
                    )
                )
            ]
        )
    )

def get_lists_view(selected_list_name, is_viewing_favourites, refresh_list_detail_view, list_detail_col, go_back_to_lists_index, run_list_shell, copy_list_command, refresh_lists_main_view, lists_main_col, content_area, bulk_action_btn=None, refresh_callback=None):
    if selected_list_name or is_viewing_favourites:
        refresh_list_detail_view()
        title = "Favourites" if is_viewing_favourites else selected_list_name
        btn_text = f"Try {title} in Shell"

        items_for_tooltip = []
        if is_viewing_favourites:
            items_for_tooltip = state.favourites
        elif selected_list_name and selected_list_name in state.saved_lists:
            items_for_tooltip = state.saved_lists[selected_list_name]

        tooltip_cmd = _build_shell_command_for_items(items_for_tooltip, with_wrapper=True) if items_for_tooltip else ""
        clean_cmd = _build_shell_command_for_items(items_for_tooltip, with_wrapper=False) if items_for_tooltip else ""
        
        header_actions = [
            bulk_action_btn if bulk_action_btn else ft.Container(),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text(btn_text, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)]),
                on_click=run_list_shell,
                bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.BLUE_600),
                blur=ft.Blur(15, 15, ft.BlurTileMode.MIRROR),
                border_radius=state.get_radius('button'),
                ink=True,
                tooltip=tooltip_cmd
            ),
            ft.IconButton(ft.Icons.CONTENT_COPY, on_click=copy_list_command, tooltip=clean_cmd)
        ]
        if refresh_callback and state.show_refresh_button:
            header_actions.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Installed Status", on_click=refresh_callback))

        return ft.Container(
            expand=True,
            padding=ft.padding.only(left=20, right=20, bottom=10),
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.padding.only(bottom=15),
                        content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back_to_lists_index), ft.Text(title, size=24, weight=ft.FontWeight.BOLD)]),
                            ft.Row(header_actions)
                        ])
                    ),
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            list_detail_col,
                            ft.Container(height=100) # Spacer for bottom nav
                        ]
                    )
                ]
            )
        )
    else:
        refresh_lists_main_view()
        return ft.Container(
            expand=True,
            padding=ft.padding.only(left=20, right=20, bottom=10),
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(
                        padding=ft.padding.only(bottom=15),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("My Lists", size=24, weight=ft.FontWeight.BOLD, color="onSurface"),
                                ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Installed Status", on_click=refresh_callback) if refresh_callback and state.show_refresh_button else ft.Container()
                            ]
                        )
                    ),
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            lists_main_col,
                            ft.Container(height=100) # Spacer for bottom nav
                        ]
                    )
                ]
            )
        )

def create_stacked_card(content, base_color, width=None, height=None, expand=1):
    container_width = width if width and width > 0 else None
    container_expand = expand if (not width or width == 0) else 0

    layer1 = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.3, base_color),
        border_radius=20,
        border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
        rotate=ft.Rotate(0.12, alignment=ft.alignment.center),
        scale=0.92,
        left=0, right=0, top=0, bottom=0,
    )

    layer2 = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.6, base_color),
        border_radius=20,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
        rotate=ft.Rotate(0.06, alignment=ft.alignment.center),
        scale=0.96,
        left=0, right=0, top=0, bottom=0,
    )

    content.left = 0
    content.right = 0
    content.top = 0
    content.bottom = 0

    return ft.Container(
        expand=container_expand,
        width=container_width,
        height=height,
        content=ft.Stack(
            controls=[
                layer1,
                layer2,
                content
            ]
        )
    )

class SongCard(GlassContainer):
    def __init__(self, data_cfg, width=None, height=None):
        self.cfg = data_cfg
        self.base_col = COLOR_NAME_MAP.get(self.cfg.get("color"), ft.Colors.BLUE)
        self.default_url = "https://song.link/https://music.youtube.com/watch?v=CzE7qEPWuG4&list=RDAMVMI7ftgtJYdgs"
        
        # Initial State
        self.title_text = "Loading Song..."
        self.artist_text = ""
        self.bg_image = None
        self.target_url = self.default_url
        self.custom_tooltip = "Song of the Day"
        
        super().__init__(
            padding=15, border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.15, self.base_col),
            content=ft.Container(), # Placeholder
            on_click=self.handle_click
        )
        self.width = width
        self.height = height
        
        self.initialize_state()
        self.update_card_content()

    def initialize_state(self):
        self.mastodon_url = ""
        if state.song_use_mastodon:
            if state.song_mastodon_cache:
                self.apply_cache_data(state.song_mastodon_cache)
        else:
            self.target_url = self.default_url
            self.custom_tooltip = f"Open in browser: {self.target_url}"
            if state.default_song_cache:
                self.title_text = state.default_song_cache.get("title", "Song of the Day")
                self.artist_text = "All-Might Pick"
                self.bg_image = state.default_song_cache.get("image")
            # Else remains Loading...

    def did_mount(self):
        # Always fetch fresh data on mount (app launch/refresh) to ensure latest link
        if state.song_use_mastodon:
            threading.Thread(target=self.fetch_mastodon_meta, daemon=True).start()
        else:
            threading.Thread(target=self.fetch_default_meta, daemon=True).start()

    def fetch_default_meta(self):
        data = fetch_opengraph_data(self.default_url)
        if data:
            data['fetched_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state.default_song_cache = data
            state.save_settings()
            self.title_text = data.get("title", "Song of the Day")
            self.artist_text = "All-Might Pick"
            self.bg_image = data.get("image")
            self.update_card_content()

    def fetch_mastodon_meta(self):
        if state.song_mastodon_cache:
            self.apply_cache_data(state.song_mastodon_cache)
            return

        fetched = get_mastodon_quote(state.song_mastodon_account, state.song_mastodon_tag)
        if fetched:
            # Parse Song Link
            text = fetched.get("text", "")
            url_match = re.search(r'(https?://\S+)', text)
            if url_match:
                song_url = url_match.group(1)
                og_data = fetch_opengraph_data(song_url)
                if og_data:
                    fetched['title'] = og_data.get('title')
                    fetched['image'] = og_data.get('image')
                    fetched['song_url'] = song_url
            
            fetched['mastodon_link'] = fetched.get('link')
            fetched['fetched_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state.song_mastodon_cache = fetched
            state.last_fetched_song = fetched
            state.save_settings()
            
            self.apply_cache_data(fetched)

    def apply_cache_data(self, data):
        self.title_text = data.get("title", data.get("text", "...").split("\n")[0])
        self.artist_text = data.get("author", "")
        self.target_url = data.get("song_url", data.get("link", ""))
        self.mastodon_url = data.get("mastodon_link", data.get("link", ""))
        self.bg_image = data.get("image")
        self.custom_tooltip = f"Song: {self.target_url}"
        self.update_card_content()

    def update_card_content(self):
        self.tooltip = "Click for options"
        self.padding = 15
        self.image_src = None # We will use a dedicated Image control, not a background

        thumbnail_control = None
        if self.bg_image:
            thumbnail_control = ft.Image(src=self.bg_image, width=80, height=80, fit=ft.ImageFit.COVER, border_radius=10)
        else:
            thumbnail_control = ft.Container(
                width=80, height=80,
                bgcolor=ft.Colors.with_opacity(0.1, state.get_base_color()),
                border_radius=10,
                alignment=ft.alignment.center,
                content=ft.Icon(ft.Icons.MUSIC_NOTE, size=40, color="onSurface")
            )

        text_content = ft.Column(
            [
                ft.Text(self.title_text, size=16, color="onSurface", weight=ft.FontWeight.BOLD, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            expand=True
        )

        self.content = ft.Column(
            [
                ft.Row([ft.Text("Song of the Day", size=12, color="onSurfaceVariant", weight=ft.FontWeight.BOLD)]),
                ft.Container(
                    content=ft.Row(
                        [
                            thumbnail_control,
                            text_content
                        ],
                        spacing=15,
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    expand=True
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER
        )
        
        if self.page: self.update()

    def handle_click(self, e):
        if not self.target_url: return

        close_func = [None]

        def open_song(e):
            e.page.launch_url(self.target_url)
            if close_func[0]: close_func[0]()

        def open_mastodon(e):
            if self.mastodon_url:
                e.page.launch_url(self.mastodon_url)
            if close_func[0]: close_func[0]()

        def refresh_meta(e):
            if close_func[0]: close_func[0]()
            if controls_mod.show_toast_global:
                controls_mod.show_toast_global("Refetching song data...")
            
            # Clear cache to force fetch
            state.song_mastodon_cache = None
            
            # Reuse the fetch method
            if state.song_use_mastodon:
                 threading.Thread(target=self.fetch_mastodon_meta, daemon=True).start()
            else:
                 threading.Thread(target=self.fetch_default_meta, daemon=True).start()

        # Get fetched time
        fetched_at = "Unknown"
        if state.song_use_mastodon and state.song_mastodon_cache:
            fetched_at = state.song_mastodon_cache.get('fetched_at', 'Unknown')
        elif not state.song_use_mastodon and state.default_song_cache:
            fetched_at = state.default_song_cache.get('fetched_at', 'Unknown')

        def copy_text(e, text):
            e.page.set_clipboard(text)
            if controls_mod.show_toast_global:
                 controls_mod.show_toast_global("Copied to clipboard")

        dlg_content = ft.Column([
            ft.Row([
                ft.ElevatedButton("Open Song Link", icon=ft.Icons.MUSIC_NOTE, on_click=open_song, width=220, tooltip=self.target_url),
                ft.IconButton(ft.Icons.COPY, tooltip="Copy Song Link", on_click=lambda e: copy_text(e, self.target_url))
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=5),
            ft.Row([
                ft.ElevatedButton("Open Mastodon Post", icon=ft.Icons.FORUM, on_click=open_mastodon, width=220, disabled=not self.mastodon_url, tooltip=self.mastodon_url),
                 ft.IconButton(ft.Icons.COPY, tooltip="Copy Mastodon Link", on_click=lambda e: copy_text(e, self.mastodon_url), disabled=not self.mastodon_url)
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            ft.Text(f"Cached: {fetched_at}", size=10, color="onSurfaceVariant", italic=True)
        ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        actions = [
            ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Metadata", on_click=refresh_meta),
            ft.TextButton("Close", on_click=lambda e: close_func[0]()),
        ]

        if controls_mod.show_glass_dialog:
             close_func[0] = controls_mod.show_glass_dialog("Link Options", dlg_content, actions)

def get_home_view():
    state.update_daily_indices()

    app_data = DAILY_APPS[state.daily_indices["app"] % len(DAILY_APPS)]
    quote_data = DAILY_QUOTES[state.daily_indices["quote"] % len(DAILY_QUOTES)]
    tip_data = DAILY_TIPS[state.daily_indices["tip"] % len(DAILY_TIPS)]
    song_data = DAILY_SONGS[state.daily_indices["song"] % len(DAILY_SONGS)]

    # --- Daily Digest Cards ---
    cards_row1 = []
    cards_row2 = []

    def get_cfg(key):
        return state.home_card_config.get(key, CARD_DEFAULTS[key])

    def get_alignment(align_str):
        if align_str == "left": return ft.MainAxisAlignment.START
        if align_str == "right": return ft.MainAxisAlignment.END
        return ft.MainAxisAlignment.CENTER

    def get_card_color(color_name):
        return COLOR_NAME_MAP.get(color_name, ft.Colors.BLUE)

    def create_dynamic_card_click_handler(link, refresh_callback=None):
        def handler(e):
            if not link: return

            close_dialog = [None]

            def copy_link(e, text_to_copy):
                e.page.set_clipboard(text_to_copy)
                if controls_mod.show_toast_global:
                    controls_mod.show_toast_global("Link copied to clipboard")

            def open_link(e):
                e.page.launch_url(link)
                if close_dialog[0]:
                    close_dialog[0]()
            
            dlg_content = ft.Column([
                ft.Row([
                     ft.ElevatedButton("Open Mastodon Post", icon=ft.Icons.FORUM, on_click=open_link, width=220, tooltip=link),
                     ft.IconButton(ft.Icons.COPY, tooltip="Copy Link", on_click=lambda e: copy_link(e, link))
                ], alignment=ft.MainAxisAlignment.CENTER),
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

            def refresh_action(e):
                if close_dialog[0]: close_dialog[0]()
                if refresh_callback:
                    if controls_mod.show_toast_global:
                        controls_mod.show_toast_global("Refetching...")
                    refresh_callback()

            actions = []
            if refresh_callback:
                actions.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", on_click=refresh_action))
            
            actions.append(ft.TextButton("Close", on_click=lambda e: close_dialog[0]()))

            close_dialog[0] = controls_mod.show_glass_dialog("Link Options", dlg_content, actions)
        return handler

    # Build App Card
    cfg = get_cfg("app")
    if cfg["visible"]:
        base_col = get_card_color(cfg["color"])
        
        app_title = app_data["pname"]
        app_desc = app_data["desc"]
        app_tooltip = "Random App"
        app_click = None

        if state.app_use_mastodon:
            if not state.app_mastodon_cache:
                fetched = get_mastodon_quote(state.app_mastodon_account, state.app_mastodon_tag, server=state.app_mastodon_server)
                if fetched:
                    state.app_mastodon_cache = fetched
                    state.last_fetched_app = fetched
                    state.save_settings()
                elif state.last_fetched_app:
                    state.app_mastodon_cache = state.last_fetched_app
            
            if state.app_mastodon_cache:
                app_title = "Community Pick"
                app_desc = state.app_mastodon_cache.get("text", "...")
                link = state.app_mastodon_cache.get("link", "")
                if link:
                    app_tooltip = f"Open on Mastodon: {link}"
                    app_click = create_dynamic_card_click_handler(link)

        main_card = GlassContainer(
            padding=20, border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.15, base_col),
            tooltip=app_tooltip,
            on_click=app_click,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Row([ft.Text("Random App of the Day", size=12, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                    ft.Row([ft.Text(app_title, size=32, color=ft.Colors.WHITE, weight=ft.FontWeight.W_900)], alignment=get_alignment(cfg["align"])),
                    ft.Row([ft.Text(app_desc, size=12, color=ft.Colors.WHITE70, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.LEFT if cfg["align"] == "left" else (ft.TextAlign.RIGHT if cfg["align"] == "right" else ft.TextAlign.CENTER))], alignment=get_alignment(cfg["align"])),
                ]
            )
        )
        cards_row1.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=2))

    # Build Tip Card
    cfg = get_cfg("tip")
    if cfg["visible"]:
        base_col = get_card_color(cfg["color"])
        
        tip_title = tip_data["title"]
        tip_code = tip_data["code"]
        tip_tooltip = "Nix Tip"
        tip_click = None

        if state.tip_use_mastodon:
            if not state.tip_mastodon_cache:
                fetched = get_mastodon_quote(state.tip_mastodon_account, state.tip_mastodon_tag, server=state.tip_mastodon_server)
                if fetched:
                    state.tip_mastodon_cache = fetched
                    state.last_fetched_tip = fetched
                    state.save_settings()
                elif state.last_fetched_tip:
                    state.tip_mastodon_cache = state.last_fetched_tip
            
            if state.tip_mastodon_cache:
                tip_title = "Community Tip"
                tip_code = state.tip_mastodon_cache.get("text", "...")
                link = state.tip_mastodon_cache.get("link", "")
                if link:
                    tip_tooltip = f"Open on Mastodon: {link}"
                    tip_click = create_dynamic_card_click_handler(link)

        main_card = GlassContainer(
            padding=15, border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.15, base_col),
            tooltip=tip_tooltip,
            on_click=tip_click,
            content=ft.Column(
                controls=[
                    ft.Row([ft.Text("Nix Random Tip", size=12, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                    ft.Container(height=10),
                    ft.Row([ft.Text(tip_title, size=16, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                    ft.Container(
                        bgcolor=ft.Colors.BLACK26, padding=10, border_radius=8,
                        content=ft.Text(tip_code, font_family="monospace", size=12, color=ft.Colors.GREEN_100),
                        alignment=ft.alignment.center_left if cfg["align"] == "left" else (ft.alignment.center_right if cfg["align"] == "right" else ft.alignment.center)
                    )
                ]
            )
        )
        cards_row1.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

    # Build Quote Card
    cfg = get_cfg("quote")
    if cfg["visible"]:
        base_col = get_card_color(cfg["color"])
        
        # Initial State (Default or Cached)
        q_text_val = quote_data["text"]
        q_tooltip_val = "Click for options"
        q_click_handler = [None] # Mutable ref for click handler

        def fetch_fresh_quote(force_refresh=False):
            # Check cache to avoid refetching on navigation unless forced
            if state.mastodon_quote_cache and not force_refresh:
                return

            if state.use_mastodon_quote:
                fetched = get_mastodon_quote(state.quote_mastodon_account, state.quote_mastodon_tag, server=state.quote_mastodon_server)
                if fetched == {}:
                    q_text_control.value = quote_data["text"]
                    q_click_handler[0] = None
                    main_card.tooltip = "Click for options"
                elif fetched:
                    state.mastodon_quote_cache = fetched
                    state.last_fetched_quote = fetched
                    state.save_settings()
                    
                    q_text_control.value = fetched.get("text", "...")
                    link = fetched.get("link", "")
                    if link:
                        main_card.tooltip = "Click for options"
                        q_click_handler[0] = create_dynamic_card_click_handler(link, refresh_quote_action)
                
                if q_text_control.page:
                    q_text_control.update()
                    main_card.update()

        def refresh_quote_action():
            state.mastodon_quote_cache = None
            threading.Thread(target=lambda: fetch_fresh_quote(force_refresh=True), daemon=True).start()

        if state.use_mastodon_quote and state.mastodon_quote_cache:
             q_text_val = state.mastodon_quote_cache.get("text", "...")
             link = state.mastodon_quote_cache.get("link", "")
             if link:
                 q_tooltip_val = "Click for options"
                 q_click_handler[0] = create_dynamic_card_click_handler(link, refresh_quote_action)

        # Controls that need updating
        q_text_control = ft.Text(
            q_text_val, 
            size=13, 
            color=ft.Colors.WHITE, 
            italic=state.quote_style_italic, 
            weight=ft.FontWeight.BOLD if state.quote_style_bold else ft.FontWeight.NORMAL,
            text_align=ft.TextAlign.LEFT if cfg["align"] == "left" else (ft.TextAlign.RIGHT if cfg["align"] == "right" else ft.TextAlign.CENTER)
        )
        
        main_card = GlassContainer(
            padding=15, border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.15, base_col),
            tooltip=q_tooltip_val,
            on_click=lambda e: q_click_handler[0](e) if q_click_handler[0] else None,
            content=ft.Column(
                controls=[
                    ft.Row([ft.Text("Quote of the Day", size=12, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                    ft.Container(expand=True, content=ft.Column([q_text_control], alignment=ft.MainAxisAlignment.CENTER))
                ]
            )
        )
        cards_row2.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

        # Background Fetch for Quote
        threading.Thread(target=fetch_fresh_quote, daemon=True).start()

    # Build Song Card
    cfg = get_cfg("song")
    if cfg["visible"]:
        base_col = get_card_color(cfg["color"])
        main_card = SongCard(cfg, width=cfg["w"], height=cfg["h"])
        cards_row2.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

    # --- Carousel Data Logic ---
    carousel_items = []
    
    # Default/Fallback to Random Tips immediately (so UI doesn't block)
    import random
    tips_pool = list(DAILY_TIPS)
    random.shuffle(tips_pool)
    selected_tips = tips_pool[:5]
    
    colors = [ft.Colors.BLUE, ft.Colors.PURPLE, ft.Colors.ORANGE, ft.Colors.TEAL, ft.Colors.INDIGO]
    for i, tip in enumerate(selected_tips):
        carousel_items.append({
            "title": tip.get("title", "Nix Tip"),
            "desc": tip.get("code", ""),
            "icon": ft.Icons.LIGHTBULB_OUTLINE,
            "color": colors[i % len(colors)]
        })
    
    # Use cached data if available
    if state.carousel_use_mastodon and state.carousel_mastodon_cache:
        cached_items = []
        for i, item in enumerate(state.carousel_mastodon_cache):
            cached_items.append({
                "title": "Community Tip",
                "desc": item.get("text", "")[:150] + "..." if len(item.get("text", "")) > 150 else item.get("text", ""),
                "icon": ft.Icons.LIGHTBULB,
                "color": colors[i % len(colors)]
            })
        if cached_items:
             carousel_items = cached_items

    carousel_widget = AutoCarousel(carousel_items)

    # Background fetch for fresh data
    def fetch_fresh_carousel_data():
        if state.carousel_use_mastodon and state.carousel_mastodon_account and state.carousel_mastodon_tag:
            try:
                feed = get_mastodon_feed(state.carousel_mastodon_account, state.carousel_mastodon_tag, limit=5, server=state.carousel_mastodon_server)
                if feed:
                    state.carousel_mastodon_cache = feed
                    state.last_fetched_carousel = feed
                    state.save_settings()
                    
                    new_items = []
                    for i, item in enumerate(feed):
                        new_items.append({
                            "title": "Community Tip",
                            "desc": item.get("text", "")[:150] + "..." if len(item.get("text", "")) > 150 else item.get("text", ""),
                            "icon": ft.Icons.LIGHTBULB,
                            "color": colors[i % len(colors)]
                        })
                    
                    if new_items:
                        carousel_widget.data_list = new_items
                        carousel_widget.current_index = 0
                        carousel_widget.update_content()
                        # carousel_widget.update() # update_content calls update if page exists
            except Exception as e:
                print(f"Background fetch failed: {e}")

    threading.Thread(target=fetch_fresh_carousel_data, daemon=True).start()

    view_controls = []

    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Column([
                ft.Row([ft.Icon(ft.Icons.HOME_FILLED, size=state.get_size(4.0), color=ft.Colors.BLUE_200)], alignment=ft.MainAxisAlignment.START),
                ft.Text(f"Hello, {state.username}!", size=state.get_size(2.3), weight=ft.FontWeight.W_900, color="onSurface"),
                ft.Text("Welcome to All Might", size=state.get_size(1.15), color="onSurfaceVariant"),
            ]),
            ft.Container(
                width=400,
                content=ft.Column([
                    ft.Text("App tips", size=12, weight=ft.FontWeight.BOLD, color="onSurfaceVariant"),
                    carousel_widget
                ])
            )
        ]
    )
    view_controls.append(header_row)

    if cards_row1 or cards_row2:
        view_controls.append(ft.Container(height=30))
        view_controls.append(ft.Text("Daily Digest", size=18, weight=ft.FontWeight.BOLD, color="onSurfaceVariant"))
        view_controls.append(ft.Container(height=10))

        if cards_row1:
            view_controls.append(ft.Row(controls=cards_row1, spacing=20, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START))
        if cards_row2:
            view_controls.append(ft.Container(height=40))
            view_controls.append(ft.Row(controls=cards_row2, spacing=20, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START))

    view_controls.append(ft.Container(height=100))

    return ft.Container(
        expand=True,
        alignment=ft.alignment.top_left,
        padding=ft.padding.only(top=40, left=30, right=30, bottom=0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.START,
            controls=view_controls,
            scroll=ft.ScrollMode.AUTO
        )
    )

def get_settings_view(page, navbar_ref, on_nav_change, show_toast, show_undo_toast, show_destructive_dialog, refresh_dropdown_options, update_badges_style, update_bg_callback=None):
    categories = ["appearance", "profile", "channels", "run_config", "home_config", "installed", "debug", "experimental"]
    initial_cat_idx = state.last_settings_category
    if initial_cat_idx < 0 or initial_cat_idx >= len(categories):
        initial_cat_idx = 0
    
    settings_scroll_ref = ft.Ref()
    settings_refresh_ref = [None]

    def on_scroll_change(e):
        state.last_settings_scroll = e.pixels

    settings_main_column = SettingsScrollColumn(
        scroll=ft.ScrollMode.HIDDEN,
        expand=True,
        ref=settings_scroll_ref,
        on_scroll=on_scroll_change,
        on_scroll_interval=10,
    )

    channels_row = ft.Row(wrap=True, spacing=10, run_spacing=10)
    new_channel_input = ft.TextField(hint_text="nixos-23.11", expand=True, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"))

    def update_username(e):
        state.username = e.control.value
        state.save_settings()
        show_toast(f"Username updated")

    def update_default_channel(e):
        state.default_channel = e.control.value
        state.save_settings()
        refresh_dropdown_options()
        show_toast(f"Saved default: {state.default_channel}")

    preview_text_normal = ft.Text("This is how your text looks.", size=state.get_font_size('body'), color="onSurface")
    preview_text_small = ft.Text("Small text example", size=state.get_font_size('small'), color="onSurfaceVariant")
    preview_text_title = ft.Text("Large Header", size=state.get_font_size('title'), weight=ft.FontWeight.BOLD)

    def refresh_fonts():
        if settings_refresh_ref[0]:
            settings_refresh_ref[0]()
        else:
            on_nav_change(4)

        if navbar_ref[0]: navbar_ref[0]()
        page.update()

    def get_label_text(label, current, default):
        return f"{label} (Cur: {int(current)} | Def: {default})"

    txt_global_font = ft.Text(get_label_text("Global Font Size", state.global_font_size, 14), weight=ft.FontWeight.BOLD)
    txt_title_font = ft.Text(get_label_text("Title Font Size", state.title_font_size, 16))
    txt_body_font = ft.Text(get_label_text("Body Font Size", state.body_font_size, 14))
    txt_small_font = ft.Text(get_label_text("Small/Tag Font Size", state.small_font_size, 12))
    txt_nav_font = ft.Text(get_label_text("Navbar Font Size", state.nav_font_size, 12))

    def update_global_font_live(e):
        val = int(e.control.value)
        state.global_font_size = val
        txt_global_font.value = get_label_text("Global Font Size", val, 14)
        txt_global_font.update()

        preview_text_normal.size = state.get_font_size('body')
        preview_text_small.size = state.get_font_size('small')
        preview_text_title.size = state.get_font_size('title')
        preview_text_normal.update()
        preview_text_small.update()
        preview_text_title.update()

    def save_and_refresh_fonts(e):
        state.save_settings()
        refresh_fonts()

    def update_title_font_live(e):
        val = int(e.control.value)
        state.title_font_size = val
        txt_title_font.value = get_label_text("Title Font Size", val, 16)
        txt_title_font.update()

        preview_text_title.size = state.get_font_size('title')
        preview_text_title.update()

    def update_sync_title(e):
        state.sync_title_font = e.control.value
        state.save_settings()
        slider_title_font.disabled = state.sync_title_font
        slider_title_font.update()
        refresh_fonts()

    def update_body_font_live(e):
        val = int(e.control.value)
        state.body_font_size = val
        txt_body_font.value = get_label_text("Body Font Size", val, 14)
        txt_body_font.update()

        preview_text_normal.size = state.get_font_size('body')
        preview_text_normal.update()

    def update_sync_body(e):
        state.sync_body_font = e.control.value
        state.save_settings()
        slider_body_font.disabled = state.sync_body_font
        slider_body_font.update()
        refresh_fonts()

    def update_small_font_live(e):
        val = int(e.control.value)
        state.small_font_size = val
        txt_small_font.value = get_label_text("Small/Tag Font Size", val, 12)
        txt_small_font.update()

        preview_text_small.size = state.get_font_size('small')
        preview_text_small.update()

    def update_sync_small(e):
        state.sync_small_font = e.control.value
        state.save_settings()
        slider_small_font.disabled = state.sync_small_font
        slider_small_font.update()
        refresh_fonts()

    def update_nav_font_live(e):
        val = int(e.control.value)
        state.nav_font_size = val
        txt_nav_font.value = get_label_text("Navbar Font Size", val, 12)
        txt_nav_font.update()

    def update_sync_nav_font(e):
        state.sync_nav_font = e.control.value
        state.save_settings()
        slider_nav_font.disabled = state.sync_nav_font
        slider_nav_font.update()
        refresh_fonts()

    def update_confirm_timer(e):
        state.confirm_timer = int(e.control.value)
        state.save_settings()

    def update_undo_timer(e):
        state.undo_timer = int(e.control.value)
        state.save_settings()

    def update_badge_size(e):
        state.nav_badge_size = int(e.control.value)
        state.save_settings()
        update_badges_style()

    def update_search_limit(e):
        state.search_limit = int(e.control.value)
        state.save_settings()

    def update_floating_nav(e):
        state.floating_nav = e.control.value
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_adaptive_nav(e):
        state.adaptive_nav = e.control.value
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_glass_nav(e):
        state.glass_nav = e.control.value
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    txt_nav_width = ft.Text(get_label_text("Total Length (Floating)", state.nav_bar_width, 500))
    txt_nav_height = ft.Text(get_label_text("Nav Bar Height", state.nav_bar_height, 80))
    txt_nav_spacing = ft.Text(get_label_text("Icon Spacing (Manual)", state.nav_icon_spacing, 15))

    def update_nav_width(e):
        val = int(e.control.value)
        state.nav_bar_width = val
        txt_nav_width.value = get_label_text("Total Length (Floating)", val, 500)
        txt_nav_width.update()
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_nav_height(e):
        val = int(e.control.value)
        state.nav_bar_height = val
        txt_nav_height.value = get_label_text("Nav Bar Height", val, 80)
        txt_nav_height.update()
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_icon_spacing(e):
        val = int(e.control.value)
        state.nav_icon_spacing = val
        txt_nav_spacing.value = get_label_text("Icon Spacing (Manual)", val, 15)
        txt_nav_spacing.update()
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_sync_nav_spacing(e):
        state.sync_nav_spacing = e.control.value
        state.save_settings()
        nav_spacing_slider.disabled = state.sync_nav_spacing
        nav_spacing_slider.update()
        if navbar_ref[0]: navbar_ref[0]()

    txt_global_radius = ft.Text(get_label_text("Global Radius", state.global_radius, 33), weight=ft.FontWeight.BOLD)
    txt_nav_radius = ft.Text(get_label_text("Nav Bar Radius", state.nav_radius, 33))
    txt_card_radius = ft.Text(get_label_text("Card Radius", state.card_radius, 15))
    txt_button_radius = ft.Text(get_label_text("Button Radius", state.button_radius, 10))
    txt_search_radius = ft.Text(get_label_text("Search Bar Radius", state.search_radius, 15))
    txt_selector_radius = ft.Text(get_label_text("Selector Radius", state.selector_radius, 15))
    txt_footer_radius = ft.Text(get_label_text("Footer Section Radius", state.footer_radius, 15))
    txt_chip_radius = ft.Text(get_label_text("Footer Chip Radius", state.chip_radius, 10))

    def update_global_radius(e):
        val = int(e.control.value)
        state.global_radius = val
        txt_global_radius.value = get_label_text("Global Radius", val, 33)
        txt_global_radius.update()
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_nav_radius(e):
        val = int(e.control.value)
        state.nav_radius = val
        txt_nav_radius.value = get_label_text("Nav Bar Radius", val, 33)
        txt_nav_radius.update()
        state.save_settings()
        if navbar_ref[0]: navbar_ref[0]()

    def update_sync_nav_radius(e):
        state.sync_nav_radius = e.control.value
        state.save_settings()
        slider_nav_radius.disabled = state.sync_nav_radius
        slider_nav_radius.update()
        if navbar_ref[0]: navbar_ref[0]()

    def update_card_radius(e):
        val = int(e.control.value)
        state.card_radius = val
        txt_card_radius.value = get_label_text("Card Radius", val, 15)
        txt_card_radius.update()
        state.save_settings()

    def update_sync_card_radius(e):
        state.sync_card_radius = e.control.value
        state.save_settings()
        slider_card_radius.disabled = state.sync_card_radius
        slider_card_radius.update()

    def update_button_radius(e):
        val = int(e.control.value)
        state.button_radius = val
        txt_button_radius.value = get_label_text("Button Radius", val, 10)
        txt_button_radius.update()
        state.save_settings()

    def update_sync_button_radius(e):
        state.sync_button_radius = e.control.value
        state.save_settings()
        slider_button_radius.disabled = state.sync_button_radius
        slider_button_radius.update()

    def update_search_radius(e):
        val = int(e.control.value)
        state.search_radius = val
        txt_search_radius.value = get_label_text("Search Bar Radius", val, 15)
        txt_search_radius.update()
        state.save_settings()

    def update_sync_search_radius(e):
        state.sync_search_radius = e.control.value
        state.save_settings()
        slider_search_radius.disabled = state.sync_search_radius
        slider_search_radius.update()

    def update_selector_radius(e):
        val = int(e.control.value)
        state.selector_radius = val
        txt_selector_radius.value = get_label_text("Selector Radius", val, 15)
        txt_selector_radius.update()
        state.save_settings()

    def update_sync_selector_radius(e):
        state.sync_selector_radius = e.control.value
        state.save_settings()
        slider_selector_radius.disabled = state.sync_selector_radius
        slider_selector_radius.update()

    def update_footer_radius(e):
        val = int(e.control.value)
        state.footer_radius = val
        txt_footer_radius.value = get_label_text("Footer Section Radius", val, 15)
        txt_footer_radius.update()
        state.save_settings()

    def update_sync_footer_radius(e):
        state.sync_footer_radius = e.control.value
        state.save_settings()
        slider_footer_radius.disabled = state.sync_footer_radius
        slider_footer_radius.update()

    def update_chip_radius(e):
        val = int(e.control.value)
        state.chip_radius = val
        txt_chip_radius.value = get_label_text("Footer Chip Radius", val, 10)
        txt_chip_radius.update()
        state.save_settings()

    def update_sync_chip_radius(e):
        state.sync_chip_radius = e.control.value
        state.save_settings()
        slider_chip_radius.disabled = state.sync_chip_radius
        slider_chip_radius.update()

    def update_carousel_timer(e):
        try:
            val = int(e.control.value)
            state.carousel_timer = val
            state.save_settings()
        except:
            pass

    def update_carousel_glass(e):
        state.carousel_glass = e.control.value
        state.save_settings()

    def reset_with_confirmation(title, default_applier, undo_state_capturer, undo_restorer):
        old_state = undo_state_capturer()
        def on_confirm(e):
            default_applier()
            state.save_settings()

            if "home" in title.lower():
                if settings_refresh_ref[0]: settings_refresh_ref[0]()
            else:
                refresh_fonts()

            def on_undo():
                undo_restorer(old_state)
                state.save_settings()
                if "home" in title.lower():
                    if settings_refresh_ref[0]: settings_refresh_ref[0]()
                else:
                    refresh_fonts()

            show_undo_toast("Reset to defaults", on_undo)

        show_destructive_dialog(title, "Are you sure you want to reset settings to defaults?", on_confirm)

    def reset_radius_defaults(e):
        def capture():
            return {
                'global': state.global_radius, 'nav': state.nav_radius, 'sync_nav': state.sync_nav_radius,
                'card': state.card_radius, 'sync_card': state.sync_card_radius, 'btn': state.button_radius, 'sync_btn': state.sync_button_radius,
                'search': state.search_radius, 'sync_search': state.sync_search_radius, 'sel': state.selector_radius, 'sync_sel': state.sync_selector_radius,
                'foot': state.footer_radius, 'sync_foot': state.sync_footer_radius, 'chip': state.chip_radius, 'sync_chip': state.sync_chip_radius
            }
        def apply():
            state.global_radius = 33; state.nav_radius = 33; state.sync_nav_radius = True
            state.card_radius = 15; state.sync_card_radius = True; state.button_radius = 10; state.sync_button_radius = True
            state.search_radius = 15; state.sync_search_radius = True; state.selector_radius = 15; state.sync_selector_radius = True
            state.footer_radius = 15; state.sync_footer_radius = True; state.chip_radius = 10; state.sync_chip_radius = True

            slider_global_radius.value = 33
            txt_global_radius.value = get_label_text("Global Radius", 33, 33)

            slider_nav_radius.value = 33
            txt_nav_radius.value = get_label_text("Nav Bar Radius", 33, 33)

            slider_card_radius.value = 15
            txt_card_radius.value = get_label_text("Card Radius", 15, 15)

            slider_button_radius.value = 10
            txt_button_radius.value = get_label_text("Button Radius", 10, 10)

            slider_search_radius.value = 15
            txt_search_radius.value = get_label_text("Search Bar Radius", 15, 15)

            slider_selector_radius.value = 15
            txt_selector_radius.value = get_label_text("Selector Radius", 15, 15)

            slider_footer_radius.value = 15
            txt_footer_radius.value = get_label_text("Footer Section Radius", 15, 15)

            slider_chip_radius.value = 10
            txt_chip_radius.value = get_label_text("Footer Chip Radius", 10, 10)

        def restore(s):
            state.global_radius = s['global']; state.nav_radius = s['nav']; state.sync_nav_radius = s['sync_nav']
            state.card_radius = s['card']; state.sync_card_radius = s['sync_card']; state.button_radius = s['btn']; state.sync_button_radius = s['sync_btn']
            state.search_radius = s['search']; state.sync_search_radius = s['sync_search']; state.selector_radius = s['sel']; state.sync_selector_radius = s['sync_sel']
            state.footer_radius = s['foot']; state.sync_footer_radius = s['sync_foot']; state.chip_radius = s['chip']; state.sync_chip_radius = s['sync_chip']

        reset_with_confirmation("Reset Appearance Defaults?", apply, capture, restore)

    def reset_navbar_defaults(e):
        def capture():
            return {'float': state.floating_nav, 'adapt': state.adaptive_nav, 'glass': state.glass_nav, 'w': state.nav_bar_width, 'h': state.nav_bar_height, 'space': state.nav_icon_spacing, 'sync_space': state.sync_nav_spacing, 'badge': state.nav_badge_size}
        def apply():
            state.floating_nav = True; state.adaptive_nav = True; state.glass_nav = True
            state.nav_bar_width = 500; state.nav_bar_height = 80; state.nav_icon_spacing = 15; state.sync_nav_spacing = True; state.nav_badge_size = 20

            nav_width_slider.value = 500
            txt_nav_width.value = get_label_text("Total Length (Floating)", 500, 500)

            nav_height_slider.value = 80
            txt_nav_height.value = get_label_text("Nav Bar Height", 80, 80)

            nav_spacing_slider.value = 15
            txt_nav_spacing.value = get_label_text("Icon Spacing (Manual)", 15, 15)

        def restore(s):
            state.floating_nav = s['float']; state.adaptive_nav = s['adapt']; state.glass_nav = s['glass']
            state.nav_bar_width = s['w']; state.nav_bar_height = s['h']; state.nav_icon_spacing = s['space']; state.sync_nav_spacing = s['sync_space']; state.nav_badge_size = s['badge']

        reset_with_confirmation("Reset Navbar Defaults?", apply, capture, restore)

    def reset_timer_defaults(e):
        def capture(): return {'confirm': state.confirm_timer, 'undo': state.undo_timer}
        def apply(): state.confirm_timer = 5; state.undo_timer = 5
        def restore(s): state.confirm_timer = s['confirm']; state.undo_timer = s['undo']

        reset_with_confirmation("Reset Timer Defaults?", apply, capture, restore)

    def reset_font_defaults(e):
        def capture():
            return {
                'global': state.global_font_size, 'title': state.title_font_size, 'sync_title': state.sync_title_font,
                'body': state.body_font_size, 'sync_body': state.sync_body_font, 'small': state.small_font_size, 'sync_small': state.sync_small_font,
                'nav': state.nav_font_size, 'sync_nav': state.sync_nav_font
            }
        def apply():
            state.global_font_size = 14; state.title_font_size = 16; state.sync_title_font = True
            state.body_font_size = 14; state.sync_body_font = True; state.small_font_size = 12; state.sync_small_font = True
            state.nav_font_size = 12; state.sync_nav_font = True

            slider_global_font.value = 14
            txt_global_font.value = get_label_text("Global Font Size", 14, 14)

            slider_title_font.value = 16
            txt_title_font.value = get_label_text("Title Font Size", 16, 16)

            slider_body_font.value = 14
            txt_body_font.value = get_label_text("Body Font Size", 14, 14)

            slider_small_font.value = 12
            txt_small_font.value = get_label_text("Small/Tag Font Size", 12, 12)

            slider_nav_font.value = 12
            txt_nav_font.value = get_label_text("Navbar Font Size", 12, 12)

        def restore(s):
            state.global_font_size = s['global']; state.title_font_size = s['title']; state.sync_title_font = s['sync_title']
            state.body_font_size = s['body']; state.sync_body_font = s['sync_body']; state.small_font_size = s['small']; state.sync_small_font = s['sync_small']
            state.nav_font_size = s['nav']; state.sync_nav_font = s['sync_nav']

        reset_with_confirmation("Reset Font Defaults?", apply, capture, restore)

    def create_card_config_tile(card_key, label):
        default = CARD_DEFAULTS[card_key]
        cfg = state.home_card_config.get(card_key, default.copy())

        txt_height = ft.Text(get_label_text("Height (px)", cfg["h"], default["h"]))
        txt_width = ft.Text(get_label_text("Width (px) [0 = Auto]", cfg["w"], default["w"]))

        def update_visible(e):
            state.home_card_config[card_key]["visible"] = e.control.value
            state.save_settings()

        def update_height(e):
            val = int(e.control.value)
            state.home_card_config[card_key]["h"] = val
            txt_height.value = get_label_text("Height (px)", val, default["h"])
            txt_height.update()
            state.save_settings()

        def update_width(e):
            val = int(e.control.value)
            state.home_card_config[card_key]["w"] = val
            txt_width.value = get_label_text("Width (px) [0 = Auto]", val, default["w"])
            txt_width.update()
            state.save_settings()

        def update_align(e):
            val = list(e.control.selected)[0]
            state.home_card_config[card_key]["align"] = val
            state.save_settings()

        def update_card_color(e):
            val = e.control.data
            state.home_card_config[card_key]["color"] = val
            state.save_settings()
            for ctrl in color_row.controls:
                is_sel = (ctrl.data == val)
                ctrl.border = ft.border.all(2, "white") if is_sel else ft.border.all(2, ft.Colors.TRANSPARENT)
            color_row.update()

        switch_visible = ft.Switch(value=cfg["visible"], on_change=update_visible)
        slider_height = ft.Slider(min=100, max=400, value=cfg["h"], label="{value}", on_change=update_height)
        slider_width = ft.Slider(min=0, max=600, value=cfg["w"], label="{value}", on_change=update_width)
        seg_align = ft.SegmentedButton(
            selected={cfg["align"]},
            on_change=update_align,
            segments=[
                ft.Segment(value="left", label=ft.Text("Left"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_LEFT)),
                ft.Segment(value="center", label=ft.Text("Center"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_CENTER)),
                ft.Segment(value="right", label=ft.Text("Right"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_RIGHT)),
            ]
        )

        color_controls = []
        for name, code in COLOR_NAME_MAP.items():
            is_selected = (name == cfg.get("color", default["color"]))
            color_controls.append(
                ft.Container(
                    width=30, height=30, border_radius=15, bgcolor=code,
                    border=ft.border.all(2, "white") if is_selected else ft.border.all(2, ft.Colors.TRANSPARENT),
                    on_click=update_card_color, data=name, ink=True, tooltip=name.capitalize()
                )
            )
        color_row = ft.Row(controls=color_controls, spacing=10, wrap=True)

        def reset_card_defaults(e):
            def capture():
                return state.home_card_config[card_key].copy()

            def apply():
                state.home_card_config[card_key] = default.copy()

                switch_visible.value = default["visible"]
                slider_height.value = default["h"]
                txt_height.value = get_label_text("Height (px)", default["h"], default["h"])

                slider_width.value = default["w"]
                txt_width.value = get_label_text("Width (px) [0 = Auto]", default["w"], default["w"])

                seg_align.selected = {default["align"]}

                for ctrl in color_row.controls:
                    ctrl.border = ft.border.all(2, "white") if ctrl.data == default["color"] else ft.border.all(2, ft.Colors.TRANSPARENT)

                if card_key == "quote":
                    state.use_mastodon_quote = True
                    state.quote_mastodon_server = "mstdn.social"
                    state.quote_mastodon_account = "vivekanandanks"
                    state.quote_mastodon_tag = "mha"
                    state.quote_style_italic = True
                    state.quote_style_bold = True
                    state.mastodon_quote_cache = None
                
                if card_key == "app":
                    state.app_use_mastodon = False
                    state.app_mastodon_server = "mstdn.social"
                    state.app_mastodon_account = ""
                    state.app_mastodon_tag = ""
                    state.app_mastodon_cache = None

                if card_key == "tip":
                    state.tip_use_mastodon = False
                    state.tip_mastodon_server = "mstdn.social"
                    state.tip_mastodon_account = ""
                    state.tip_mastodon_tag = ""
                    state.tip_mastodon_cache = None

                if card_key == "song":
                    state.song_use_mastodon = False
                    state.song_mastodon_server = "mstdn.social"
                    state.song_mastodon_account = ""
                    state.song_mastodon_tag = ""
                    state.song_mastodon_cache = None

                if card_key == "carousel":
                    state.carousel_use_mastodon = True
                    state.carousel_mastodon_server = "mstdn.social"
                    state.carousel_mastodon_account = ""
                    state.carousel_mastodon_tag = ""
                    state.carousel_mastodon_cache = None

                if settings_main_column.page:
                    switch_visible.update()
                    slider_height.update()
                    txt_height.update()
                    slider_width.update()
                    txt_width.update()
                    seg_align.update()
                    color_row.update()
                    if card_key in ["quote", "app", "tip", "song"]:
                        update_settings_view()

            def restore(s):
                state.home_card_config[card_key] = s

            reset_with_confirmation(f"Reset {label}?", apply, capture, restore)

        tile_content = [
            ft.Row([ft.Text("Show Card:", weight=ft.FontWeight.BOLD), switch_visible], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            txt_height, slider_height,
            txt_width, slider_width,
            ft.Text("Content Alignment:"), seg_align,
            ft.Container(height=10),
            ft.Text(f"Card Color (Def: {default['color'].capitalize()})"), color_row
        ]

        if card_key == "quote":
            def update_use_mastodon(e):
                state.use_mastodon_quote = e.control.value
                state.save_settings()
                state.mastodon_quote_cache = None # Clear cache to force refresh

            def update_mastodon_server(e):
                state.quote_mastodon_server = e.control.value
                state.save_settings()
                state.mastodon_quote_cache = None

            def update_mastodon_account(e):
                state.quote_mastodon_account = e.control.value
                state.save_settings()
                state.mastodon_quote_cache = None

            def update_mastodon_tag(e):
                state.quote_mastodon_tag = e.control.value
                state.save_settings()
                state.mastodon_quote_cache = None

            def update_quote_italic(e):
                state.quote_style_italic = e.control.value
                state.save_settings()

            def update_quote_bold(e):
                state.quote_style_bold = e.control.value
                state.save_settings()

            tile_content.extend([
                ft.Divider(),
                ft.Text("Dynamic Source (Mastodon)", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Enable RSS Fetch:"), ft.Switch(value=state.use_mastodon_quote, on_change=update_use_mastodon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.TextField(label="Server (e.g. mstdn.social)", value=state.quote_mastodon_server, on_blur=update_mastodon_server, text_size=12),
                ft.TextField(label="Account (e.g. vivekanandanks)", value=state.quote_mastodon_account, on_blur=update_mastodon_account, text_size=12),
                ft.TextField(label="Tag (e.g. mha)", value=state.quote_mastodon_tag, on_blur=update_mastodon_tag, text_size=12),
                ft.Container(height=10),
                ft.Text("Quote Style", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Italic Text:"), ft.Switch(value=state.quote_style_italic, on_change=update_quote_italic)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Bold Text:"), ft.Switch(value=state.quote_style_bold, on_change=update_quote_bold)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ])

        elif card_key == "app":
            def update_app_mastodon(e):
                state.app_use_mastodon = e.control.value
                state.save_settings()
                state.app_mastodon_cache = None

            def update_app_server(e):
                state.app_mastodon_server = e.control.value
                state.save_settings()
                state.app_mastodon_cache = None

            def update_app_account(e):
                state.app_mastodon_account = e.control.value
                state.save_settings()
                state.app_mastodon_cache = None

            def update_app_tag(e):
                state.app_mastodon_tag = e.control.value
                state.save_settings()
                state.app_mastodon_cache = None

            tile_content.extend([
                ft.Divider(),
                ft.Text("Dynamic Source (Mastodon)", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Enable RSS Fetch:"), ft.Switch(value=state.app_use_mastodon, on_change=update_app_mastodon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.TextField(label="Server", value=state.app_mastodon_server, on_blur=update_app_server, text_size=12),
                ft.TextField(label="Account", value=state.app_mastodon_account, on_blur=update_app_account, text_size=12),
                ft.TextField(label="Tag", value=state.app_mastodon_tag, on_blur=update_app_tag, text_size=12),
            ])

        elif card_key == "tip":
            def update_tip_mastodon(e):
                state.tip_use_mastodon = e.control.value
                state.save_settings()
                state.tip_mastodon_cache = None

            def update_tip_server(e):
                state.tip_mastodon_server = e.control.value
                state.save_settings()
                state.tip_mastodon_cache = None

            def update_tip_account(e):
                state.tip_mastodon_account = e.control.value
                state.save_settings()
                state.tip_mastodon_cache = None

            def update_tip_tag(e):
                state.tip_mastodon_tag = e.control.value
                state.save_settings()
                state.tip_mastodon_cache = None

            tile_content.extend([
                ft.Divider(),
                ft.Text("Dynamic Source (Mastodon)", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Enable RSS Fetch:"), ft.Switch(value=state.tip_use_mastodon, on_change=update_tip_mastodon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.TextField(label="Server", value=state.tip_mastodon_server, on_blur=update_tip_server, text_size=12),
                ft.TextField(label="Account", value=state.tip_mastodon_account, on_blur=update_tip_account, text_size=12),
                ft.TextField(label="Tag", value=state.tip_mastodon_tag, on_blur=update_tip_tag, text_size=12),
            ])

        elif card_key == "song":
            def update_song_mastodon(e):
                state.song_use_mastodon = e.control.value
                state.save_settings()
                state.song_mastodon_cache = None

            def update_song_server(e):
                state.song_mastodon_server = e.control.value
                state.save_settings()
                state.song_mastodon_cache = None

            def update_song_account(e):
                state.song_mastodon_account = e.control.value
                state.save_settings()
                state.song_mastodon_cache = None

            def update_song_tag(e):
                state.song_mastodon_tag = e.control.value
                state.save_settings()
                state.song_mastodon_cache = None

            tile_content.extend([
                ft.Divider(),
                ft.Text("Dynamic Source (Mastodon)", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Enable RSS Fetch:"), ft.Switch(value=state.song_use_mastodon, on_change=update_song_mastodon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.TextField(label="Server", value=state.song_mastodon_server, on_blur=update_song_server, text_size=12),
                ft.TextField(label="Account", value=state.song_mastodon_account, on_blur=update_song_account, text_size=12),
                ft.TextField(label="Tag", value=state.song_mastodon_tag, on_blur=update_song_tag, text_size=12),
            ])

        elif card_key == "carousel":
            def update_carousel_mastodon(e):
                state.carousel_use_mastodon = e.control.value
                state.save_settings()
                state.carousel_mastodon_cache = None

            def update_carousel_server(e):
                state.carousel_mastodon_server = e.control.value
                state.save_settings()
                state.carousel_mastodon_cache = None

            def update_carousel_account(e):
                state.carousel_mastodon_account = e.control.value
                state.save_settings()
                state.carousel_mastodon_cache = None

            def update_carousel_tag(e):
                state.carousel_mastodon_tag = e.control.value
                state.save_settings()
                state.carousel_mastodon_cache = None

            tile_content.extend([
                ft.Divider(),
                ft.Text("Dynamic Source (Mastodon)", weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Enable RSS Fetch:"), ft.Switch(value=state.carousel_use_mastodon, on_change=update_carousel_mastodon)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.TextField(label="Server", value=state.carousel_mastodon_server, on_blur=update_carousel_server, text_size=12),
                ft.TextField(label="Account", value=state.carousel_mastodon_account, on_blur=update_carousel_account, text_size=12),
                ft.TextField(label="Tag", value=state.carousel_mastodon_tag, on_blur=update_carousel_tag, text_size=12),
            ])

        return make_settings_tile(label, tile_content, reset_func=reset_card_defaults)

    def get_settings_controls(category):
        controls_list = []
        if category == "home_config":
            carousel_timer_input = ft.TextField(value=str(state.carousel_timer), hint_text="Def: 10", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_carousel_timer, on_blur=update_carousel_timer)
            controls_list = [
                ft.Text("Home Page Configuration", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                ft.Row([ft.Text("Carousel Timer (s):"), carousel_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Countdown Effect Animation:"), ft.Switch(value=state.carousel_glass, on_change=update_carousel_glass)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=10),
                create_card_config_tile("carousel", "App Tips Carousel"),
                ft.Container(height=10),
                create_card_config_tile("app", "Random App Card"),
                ft.Container(height=10),
                create_card_config_tile("quote", "Quote Card"),
                ft.Container(height=10),
                create_card_config_tile("tip", "Nix Tip Card"),
                ft.Container(height=10),
                create_card_config_tile("song", "Song Card"),
            ]
        elif category == "profile":
            username_input = ft.TextField(value=state.username, on_submit=update_username, on_blur=update_username, width=200, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"))
            controls_list = [
                ft.Text("User Profile", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                make_settings_tile("User Identity", [
                    ft.Text("Customize your user identity within the app."),
                    ft.Container(height=10),
                    ft.Row([ft.Text("Username:", weight=ft.FontWeight.BOLD, color="onSurface", width=100), username_input], alignment=ft.MainAxisAlignment.START)
                ])
            ]
        elif category == "appearance":
            # Removed Theme Mode Segment per user request (Enforced Dark Mode)

            # Background Image Controls
            bg_image_input = ft.TextField(
                value=state.background_image if state.background_image else "",
                hint_text="URL or Local Path",
                expand=True,
                text_size=12,
                content_padding=10,
                filled=True,
                bgcolor=ft.Colors.with_opacity(0.1, "onSurface")
            )

            def handle_bg_change_with_revert(new_bg, new_opacity=None, new_blur=None):
                old_bg = state.background_image
                old_opacity = state.background_opacity
                old_blur = state.background_blur
                
                # Apply new
                state.background_image = new_bg
                if new_opacity is not None:
                    state.background_opacity = new_opacity
                if new_blur is not None:
                    state.background_blur = new_blur
                
                state.save_settings()
                if update_bg_callback: update_bg_callback()
                if navbar_ref[0]: navbar_ref[0]()
                page.update()

                # Revert Logic
                def revert_func():
                    state.background_image = old_bg
                    state.background_opacity = old_opacity
                    state.background_blur = old_blur
                    state.save_settings()
                    
                    bg_image_input.value = old_bg if old_bg else ""
                    bg_opacity_slider.value = old_opacity
                    txt_bg_opacity.value = f"{int(old_opacity * 100)}%"
                    bg_blur_slider.value = old_blur
                    txt_bg_blur.value = f"{int(old_blur)} px"
                    
                    if update_bg_callback: update_bg_callback()
                    if navbar_ref[0]: navbar_ref[0]()
                    page.update()
                    if show_toast: show_toast("Reverted background")

                def keep_func():
                    if show_toast: show_toast("Background kept")

                # Show Revert Toast (15s)
                if controls_mod.show_delayed_toast_global:
                     controls_mod.show_delayed_toast_global("Reverting background in 15s...", revert_func, duration=15, cancel_text="KEEP", on_cancel=keep_func, immediate_action_text="REVERT")

            def update_bg_image(e):
                val = bg_image_input.value.strip()
                new_bg = val if val else None
                if new_bg != state.background_image:
                    handle_bg_change_with_revert(new_bg)

            bg_image_input.on_submit = update_bg_image
            bg_image_input.on_blur = update_bg_image

            def pick_bg_file(e: ft.FilePickerResultEvent):
                if e.files:
                    path = e.files[0].path
                    bg_image_input.value = path
                    handle_bg_change_with_revert(path)

            bg_file_picker = ft.FilePicker(on_result=pick_bg_file)
            if bg_file_picker not in page.overlay:
                page.overlay.append(bg_file_picker)
                page.update()

            def clear_bg_image(e):
                if state.background_image:
                    bg_image_input.value = ""
                    handle_bg_change_with_revert(None)

            bg_image_row = ft.Row([
                bg_image_input,
                ft.IconButton(ft.Icons.IMAGE, tooltip="Select File", on_click=lambda _: bg_file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)),
                ft.IconButton(ft.Icons.CLEAR, tooltip="Clear", on_click=clear_bg_image)
            ])

            # Brightness/Opacity Slider
            txt_bg_opacity = ft.Text(f"{int(state.background_opacity * 100)}%", size=12, width=40)
            def update_bg_opacity(e):
                val = float(e.control.value)
                state.background_opacity = val / 100.0
                txt_bg_opacity.value = f"{int(val)}%"
                txt_bg_opacity.update()
                state.save_settings()
                if update_bg_callback: update_bg_callback()
            
            bg_opacity_slider = ft.Slider(min=0, max=100, divisions=100, value=state.background_opacity * 100, label="{value}%", on_change=update_bg_opacity, expand=True)

            # Blur Slider
            txt_bg_blur = ft.Text(f"{int(state.background_blur)} px", size=12, width=40)
            def update_bg_blur(e):
                val = float(e.control.value)
                state.background_blur = val
                txt_bg_blur.value = f"{int(val)} px"
                txt_bg_blur.update()
                state.save_settings()
                if update_bg_callback: update_bg_callback()

            bg_blur_slider = ft.Slider(min=0, max=50, divisions=50, value=state.background_blur, label="{value}", on_change=update_bg_blur, expand=True)

            # Rotation
            txt_bg_rot_speed = ft.Text(f"{state.bg_rotation_speed}x", size=12, width=40)
            def update_bg_rot(e):
                state.bg_rotation = e.control.value
                state.save_settings()
                if update_bg_callback: update_bg_callback()

            def update_bg_rot_speed(e):
                val = float(e.control.value)
                state.bg_rotation_speed = val
                txt_bg_rot_speed.value = f"{val}x"
                txt_bg_rot_speed.update()
                state.save_settings()
                if update_bg_callback: update_bg_callback()
            
            bg_rot_speed_slider = ft.Slider(min=0.1, max=5.0, divisions=49, value=state.bg_rotation_speed, label="{value}x", on_change=update_bg_rot_speed, expand=True)

            txt_bg_rot_scale = ft.Text(f"{state.bg_rotation_scale}x", size=12, width=40)
            def update_bg_rot_scale(e):
                val = float(e.control.value)
                state.bg_rotation_scale = val
                txt_bg_rot_scale.value = f"{val}x"
                txt_bg_rot_scale.update()
                state.save_settings()
                if update_bg_callback: update_bg_callback()
            
            bg_rot_scale_slider = ft.Slider(min=1.0, max=3.0, divisions=20, value=state.bg_rotation_scale, label="{value}x", on_change=update_bg_rot_scale, expand=True)

            slider_global_radius = ft.Slider(min=0, max=50, value=state.global_radius, label="{value}", on_change=update_global_radius, on_change_end=save_and_refresh_fonts)
            slider_nav_radius = ft.Slider(min=0, max=50, value=state.nav_radius, label="{value}", on_change=update_nav_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_nav_radius)
            slider_card_radius = ft.Slider(min=0, max=50, value=state.card_radius, label="{value}", on_change=update_card_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_card_radius)
            slider_button_radius = ft.Slider(min=0, max=50, value=state.button_radius, label="{value}", on_change=update_button_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_button_radius)
            slider_search_radius = ft.Slider(min=0, max=50, value=state.search_radius, label="{value}", on_change=update_search_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_search_radius)
            slider_selector_radius = ft.Slider(min=0, max=50, value=state.selector_radius, label="{value}", on_change=update_selector_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_selector_radius)
            slider_footer_radius = ft.Slider(min=0, max=50, value=state.footer_radius, label="{value}", on_change=update_footer_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_footer_radius)
            slider_chip_radius = ft.Slider(min=0, max=50, value=state.chip_radius, label="{value}", on_change=update_chip_radius, on_change_end=save_and_refresh_fonts, disabled=state.sync_chip_radius)

            nav_width_slider = ft.Slider(min=300, max=800, value=state.nav_bar_width, label="{value}", on_change=update_nav_width)
            nav_height_slider = ft.Slider(min=50, max=120, value=state.nav_bar_height, label="{value}", on_change=update_nav_height)
            nav_spacing_slider = ft.Slider(min=0, max=50, value=state.nav_icon_spacing, label="{value}", on_change=update_icon_spacing, disabled=state.sync_nav_spacing)
            badge_size_input = ft.TextField(value=str(state.nav_badge_size), width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_badge_size, on_blur=update_badge_size)
            confirm_timer_input = ft.TextField(value=str(state.confirm_timer), width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_confirm_timer, on_blur=update_confirm_timer)
            undo_timer_input = ft.TextField(value=str(state.undo_timer), width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_undo_timer, on_blur=update_undo_timer)

            slider_global_font = ft.Slider(min=8, max=24, value=state.global_font_size, label="{value}", on_change=update_global_font_live, on_change_end=save_and_refresh_fonts)
            slider_title_font = ft.Slider(min=8, max=32, value=state.title_font_size, label="{value}", on_change=update_title_font_live, on_change_end=save_and_refresh_fonts, disabled=state.sync_title_font)
            slider_body_font = ft.Slider(min=8, max=24, value=state.body_font_size, label="{value}", on_change=update_body_font_live, on_change_end=save_and_refresh_fonts, disabled=state.sync_body_font)
            slider_small_font = ft.Slider(min=6, max=18, value=state.small_font_size, label="{value}", on_change=update_small_font_live, on_change_end=save_and_refresh_fonts, disabled=state.sync_small_font)
            slider_nav_font = ft.Slider(min=6, max=18, value=state.nav_font_size, label="{value}", on_change=update_nav_font_live, on_change_end=save_and_refresh_fonts, disabled=state.sync_nav_font)

            # --- Moved from Experimental ---
            def update_fetch_icons(e):
                state.fetch_icons = e.control.value
                state.save_settings()

            def update_icon_size(e):
                state.icon_size = int(e.control.value)
                state.save_settings()
                txt_icon_size.value = f"Icon Size (Cur: {int(e.control.value)} | Def: 48)"
                txt_icon_size.update()

            def update_channel_selector_style(e):
                state.channel_selector_style = e.control.selected.pop()
                state.save_settings()

            txt_icon_size = ft.Text(f"Icon Size (Cur: {state.icon_size} | Def: 48)")
            # -------------------------------

            controls_list = [
                ft.Text("Appearance", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                make_settings_tile("Theme", [
                    ft.Text("Background Image:", weight=ft.FontWeight.BOLD), bg_image_row,
                    ft.Container(height=10),
                    ft.Text("Background Brightness:", weight=ft.FontWeight.BOLD), 
                    ft.Row([bg_opacity_slider, txt_bg_opacity], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=5),
                    ft.Text("Background Blur:", weight=ft.FontWeight.BOLD), 
                    ft.Row([bg_blur_slider, txt_bg_blur], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=5),
                    ft.Row([ft.Text("Rotate Background:", weight=ft.FontWeight.BOLD), ft.Switch(value=state.bg_rotation, on_change=update_bg_rot)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Speed:", size=12), bg_rot_speed_slider, txt_bg_rot_speed], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Scale:", size=12), bg_rot_scale_slider, txt_bg_rot_scale], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ]),
                ft.Container(height=10),
                make_settings_tile("Radius", [
                    txt_global_radius, slider_global_radius,
                    ft.Row([txt_nav_radius, ft.Switch(value=state.sync_nav_radius, label="Global", on_change=update_sync_nav_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_nav_radius,
                    ft.Row([txt_card_radius, ft.Switch(value=state.sync_card_radius, label="Global", on_change=update_sync_card_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_card_radius,
                    ft.Row([txt_button_radius, ft.Switch(value=state.sync_button_radius, label="Global", on_change=update_sync_button_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_button_radius,
                    ft.Row([txt_search_radius, ft.Switch(value=state.sync_search_radius, label="Global", on_change=update_sync_search_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_search_radius,
                    ft.Row([txt_selector_radius, ft.Switch(value=state.sync_selector_radius, label="Global", on_change=update_sync_selector_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_selector_radius,
                    ft.Row([txt_footer_radius, ft.Switch(value=state.sync_footer_radius, label="Global", on_change=update_sync_footer_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_footer_radius,
                    ft.Row([txt_chip_radius, ft.Switch(value=state.sync_chip_radius, label="Global", on_change=update_sync_chip_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_chip_radius,
                ], reset_func=reset_radius_defaults),
                ft.Container(height=10),
                make_settings_tile("Navigation Bar", [
                    ft.Row([ft.Text("Always Floating:"), ft.Switch(value=state.floating_nav, on_change=update_floating_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Adaptive Expansion:"), ft.Switch(value=state.adaptive_nav, on_change=update_adaptive_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    txt_nav_width, nav_width_slider,
                    txt_nav_height, nav_height_slider,
                    ft.Row([ft.Text("Sync Icon Spacing:"), ft.Switch(value=state.sync_nav_spacing, on_change=update_sync_nav_spacing)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), txt_nav_spacing, nav_spacing_slider, ft.Container(height=10),
                    ft.Row([ft.Text("Glass Effect:"), ft.Switch(value=state.glass_nav, on_change=update_glass_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=10),
                    ft.Row([ft.Text("Nav Badge Size:"), badge_size_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], reset_func=reset_navbar_defaults),
                ft.Container(height=10),
                make_settings_tile("Timers", [
                    ft.Row([ft.Text("Confirm Dialog (s):"), confirm_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=10),
                    ft.Row([ft.Text("Undo Toast (s):"), undo_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], reset_func=reset_timer_defaults),
                ft.Container(height=10),
                make_settings_tile("Fonts", [
                    txt_global_font, slider_global_font,
                    ft.Divider(),
                    ft.Row([txt_title_font, ft.Switch(value=state.sync_title_font, label="Global", on_change=update_sync_title)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_title_font,
                    ft.Row([txt_body_font, ft.Switch(value=state.sync_body_font, label="Global", on_change=update_sync_body)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_body_font,
                    ft.Row([txt_small_font, ft.Switch(value=state.sync_small_font, label="Global", on_change=update_sync_small)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_small_font,
                    ft.Row([txt_nav_font, ft.Switch(value=state.sync_nav_font, label="Global", on_change=update_sync_nav_font)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_nav_font,
                    ft.Container(height=10),
                    ft.Container(
                        padding=20, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), border_radius=10,
                        content=ft.Column([
                            ft.Text("Live Preview", size=12, color="onSurfaceVariant", weight=ft.FontWeight.BOLD),
                            ft.Divider(),
                            preview_text_normal,
                            preview_text_small,
                            preview_text_title
                        ])
                    )
                ], reset_func=reset_font_defaults),
                ft.Container(height=10),
                make_settings_tile("UI Options", [
                    ft.Row([ft.Text("Fetch Icons for Search Results:"), ft.Switch(value=state.fetch_icons, on_change=update_fetch_icons)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=10),
                    txt_icon_size,
                    ft.Slider(min=24, max=96, value=state.icon_size, label="{value}", on_change=update_icon_size),
                    ft.Container(height=10),
                    ft.Text("Channel Selector Style:"),
                    ft.SegmentedButton(
                        selected={state.channel_selector_style},
                        on_change=update_channel_selector_style,
                        segments=[
                            ft.Segment(value="dropdown", label=ft.Text("Dropdown")),
                            ft.Segment(value="plain", label=ft.Text("Plain")),
                        ]
                    )
                ])
            ]
        elif category == "channels":
            search_limit_input = ft.TextField(value=str(state.search_limit), width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_search_limit, on_blur=update_search_limit)

            def add_custom_channel(e):
                ch_name = new_channel_input.value.strip()
                if state.add_channel(ch_name):
                    new_channel_input.value = ""
                    update_channel_list()
                    refresh_dropdown_options()
                    show_toast(f"Added channel: {ch_name}")
                else:
                    show_toast(f"Channel already exists")

            def remove_channel_dialog(channel_name):
                def do_remove(e):
                    state.remove_channel(channel_name)
                    update_channel_list()
                    refresh_dropdown_options()
                    show_toast(f"Removed channel: {channel_name}")
                show_destructive_dialog("Remove Channel?", f"Are you sure you want to remove '{channel_name}'?", do_remove)
            
            def toggle_channel_active(channel_name, is_active):
                state.toggle_channel(channel_name, is_active)
                refresh_dropdown_options()
                show_toast(f"{channel_name} is now {'active' if is_active else 'inactive'}")

            def update_channel_list():
                channels_row.controls.clear()
                for channel in state.available_channels:
                    is_active = channel in state.active_channels
                    chip = ft.Chip(
                        label=ft.Text(channel),
                        selected=is_active,
                        on_select=lambda e, ch=channel: toggle_channel_active(ch, e.control.selected),
                        on_delete=(lambda e, ch=channel: remove_channel_dialog(ch)) if channel != "nixos-unstable" else None,
                        delete_icon=ft.Icon(ft.Icons.DELETE_OUTLINE),
                        delete_icon_color=ft.Colors.RED_400
                    )
                    channels_row.controls.append(chip)
                if channels_row.page: channels_row.update()

            update_channel_list()

            # Suggestion Logic
            today = datetime.date.today()
            yy = today.year % 100
            month = today.month
            
            if month >= 11:
                prev_ver = f"{yy}.11"
                next_ver = f"{yy+1:02d}.05"
            elif month >= 5:
                prev_ver = f"{yy:02d}.05"
                next_ver = f"{yy}.11"
            else:
                prev_ver = f"{yy-1}.11"
                next_ver = f"{yy:02d}.05"

            suggestion_text = f"Suggested: nixos-unstable, nixos-{prev_ver}, nixos-{next_ver}"

            controls_list = [
                ft.Text("Channel & Search", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                make_settings_tile("Search Configuration", [
                    ft.Text("Search Limit", weight=ft.FontWeight.BOLD), ft.Row([ft.Text("Max results:", size=12), search_limit_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=20),
                    ft.Text("Default Search Channel", weight=ft.FontWeight.BOLD), ft.Container(height=5), ft.Dropdown(options=[ft.dropdown.Option(c) for c in state.available_channels], value=state.default_channel, on_change=update_default_channel, bgcolor="surfaceVariant", border_color="outline", text_style=ft.TextStyle(color="onSurface"), filled=True)
                ]),
                ft.Container(height=10),
                make_settings_tile("Channel Management", [
                    ft.Text("Available Channels", weight=ft.FontWeight.BOLD), ft.Container(height=10), channels_row, ft.Divider(color=ft.Colors.OUTLINE, height=20),
                    ft.Row([ft.Text("Add Channel:", size=12), new_channel_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN, on_click=add_custom_channel)]),
                    ft.Text(suggestion_text, size=11, color="onSurfaceVariant", italic=True)
                ])
            ]
        elif category == "run_config":
            cmd_preview_single = ft.Text(f"Preview: {state.shell_single_prefix} nix run nixpkgs/unstable#cowsay {state.shell_single_suffix}", size=12, color="onSurfaceVariant", font_family="monospace")
            cmd_preview_cart = ft.Text(f"Preview: {state.shell_cart_prefix} nix shell nixpkgs/unstable#vim nixpkgs/unstable#git {state.shell_cart_suffix}", size=12, color="onSurfaceVariant", font_family="monospace")

            def update_shell_single_prefix(e):
                state.shell_single_prefix = e.control.value
                state.save_settings()
                cmd_preview_single.value = f"Preview: {state.shell_single_prefix} nix run nixpkgs/unstable#cowsay {state.shell_single_suffix}"
                cmd_preview_single.update()

            def update_shell_single_suffix(e):
                state.shell_single_suffix = e.control.value
                state.save_settings()
                cmd_preview_single.value = f"Preview: {state.shell_single_prefix} nix run nixpkgs/unstable#cowsay {state.shell_single_suffix}"
                cmd_preview_single.update()

            def update_shell_cart_prefix(e):
                state.shell_cart_prefix = e.control.value
                state.save_settings()
                cmd_preview_cart.value = f"Preview: {state.shell_cart_prefix} nix shell nixpkgs/unstable#vim nixpkgs/unstable#git {state.shell_cart_suffix}"
                cmd_preview_cart.update()

            def update_shell_cart_suffix(e):
                state.shell_cart_suffix = e.control.value
                state.save_settings()
                cmd_preview_cart.value = f"Preview: {state.shell_cart_prefix} nix shell nixpkgs/unstable#vim nixpkgs/unstable#git {state.shell_cart_suffix}"
                cmd_preview_cart.update()
            
            controls_list = [
                 ft.Text("Run Configurations", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                 make_settings_tile("Single App Execution", [
                    ft.Text("Run without installing cmd config", weight=ft.FontWeight.BOLD), ft.Container(height=5),
                    ft.Text("Prefix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_single_prefix, hint_text="nix run", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_prefix),
                    ft.Text("Suffix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_single_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_suffix), cmd_preview_single
                  ]),
                  ft.Container(height=10),
                  make_settings_tile("Cart/List Execution", [
                    ft.Text("Cart/List try in shell cmd config", weight=ft.FontWeight.BOLD), ft.Container(height=5),
                    ft.Text("Prefix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_cart_prefix, hint_text="nix shell", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_prefix),
                    ft.Text("Suffix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_cart_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_suffix), cmd_preview_cart
                ])
            ]
        elif category == "installed":
            def update_auto_refresh(e):
                state.auto_refresh_ui = e.control.value
                state.save_settings()

            def update_refresh_interval(e):
                try:
                    val = int(e.control.value)
                    if val < 1: val = 1
                    state.auto_refresh_interval = val
                    state.save_settings()
                except:
                    pass

            interval_input = ft.TextField(value=str(state.auto_refresh_interval), width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_refresh_interval, on_blur=update_refresh_interval)

            controls_list = [
                ft.Text("Installed Apps", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                make_settings_tile("Refresh Settings", [
                    ft.Text("Auto Refresh UI", weight=ft.FontWeight.BOLD),
                    ft.Text("Automatically check installed packages status in background.", size=12, color="onSurfaceVariant"),
                    ft.Container(height=10),
                    ft.Row([ft.Text("Enable Auto Refresh:"), ft.Switch(value=state.auto_refresh_ui, on_change=update_auto_refresh)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Interval (seconds):"), interval_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ])
            ]
        elif category == "debug":
            def update_show_refresh(e):
                state.show_refresh_button = e.control.value
                state.save_settings()

            controls_list = [
                ft.Text("Debug Settings", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                make_settings_tile("UI Options", [
                    ft.Row([ft.Text("Show Refresh Button:"), ft.Switch(value=state.show_refresh_button, on_change=update_show_refresh)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ])
            ]
        elif category == "experimental":
            controls_list = [
                ft.Text("Experimental Settings", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                ft.Text("No experimental settings currently.", color="onSurfaceVariant")
            ]
        return controls_list

    def update_settings_view():
        idx = state.last_settings_category
        if idx < 0 or idx >= len(categories): idx = 0
        current_cat = categories[idx]
        
        settings_main_column.controls = get_settings_controls(current_cat)

        if settings_main_column.page:
            if settings_scroll_ref.current:
                try:
                    settings_scroll_ref.current.scroll_to(offset=state.last_settings_scroll, duration=0)
                except:
                    pass

            settings_main_column.update()

    def change_theme(theme):
        state.theme_mode = theme
        page.theme_mode = ft.ThemeMode.DARK if theme == "dark" else ft.ThemeMode.LIGHT
        state.save_settings()
        page.update()

    def change_color_scheme(color):
        state.theme_color = color
        page.theme = ft.Theme(color_scheme_seed=color)
        state.save_settings()
        page.update()

    def on_settings_nav_change(e):
        idx = e.control.selected_index
        state.last_settings_category = idx
        state.last_settings_scroll = 0 # Reset scroll on category change
        state.save_settings()
        update_settings_view()
    
    settings_nav_rail = ft.NavigationRail(
        selected_index=initial_cat_idx,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        group_alignment=-0.9,
        bgcolor=ft.Colors.TRANSPARENT,
        on_change=on_settings_nav_change,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.PALETTE_OUTLINED, selected_icon=ft.Icons.PALETTE, label="Appearance"),
            ft.NavigationRailDestination(icon=ft.Icons.PERSON_OUTLINE, selected_icon=ft.Icons.PERSON, label="Profile"),
            ft.NavigationRailDestination(icon=ft.Icons.TV_OUTLINED, selected_icon=ft.Icons.TV, label="Channels"),
            ft.NavigationRailDestination(icon=ft.Icons.PLAY_CIRCLE_OUTLINED, selected_icon=ft.Icons.PLAY_CIRCLE_FILLED, label="Run Config"),
            ft.NavigationRailDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home Config"),
            ft.NavigationRailDestination(icon=ft.Icons.APPS_OUTLINED, selected_icon=ft.Icons.APPS, label="Installed"),
            ft.NavigationRailDestination(icon=ft.Icons.BUG_REPORT_OUTLINED, selected_icon=ft.Icons.BUG_REPORT, label="Debug"),
            ft.NavigationRailDestination(icon=ft.Icons.SCIENCE_OUTLINED, selected_icon=ft.Icons.SCIENCE, label="Experimental"),
        ]
    )
    
    settings_content_area = ft.Container(
        expand=True, 
        padding=ft.padding.only(left=20), 
        content=ft.Column(
            expand=True,
            controls=[
                settings_main_column,
                ft.Container(height=100) # Spacer for bottom nav
            ]
        )
    )
    settings_refresh_ref[0] = update_settings_view

    update_settings_view()

    return ft.Container(padding=20, content=ft.Row(spacing=0, vertical_alignment=ft.CrossAxisAlignment.START, controls=[ft.Container(width=200, content=settings_nav_rail, border=ft.border.only(right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), padding=ft.padding.only(right=10)), settings_content_area], expand=True))

def make_settings_tile(title, controls, reset_func=None):
    expansion_controls = []
    if reset_func:
        reset_btn = ft.TextButton("Reset to defaults", icon=ft.Icons.RESTORE, on_click=reset_func, style=ft.ButtonStyle(color="onSurfaceVariant"))
        expansion_controls.append(ft.Row([reset_btn], alignment=ft.MainAxisAlignment.END))
        expansion_controls.append(ft.Divider(color="outline"))
    
    expansion_controls.extend(controls)

    def on_tile_change(e):
        is_expanded_now = (e.data == "true")
        state.last_settings_expanded[title] = is_expanded_now
        state.save_settings()

    is_expanded = state.last_settings_expanded.get(title, False)

    return ft.Container(
        border_radius=15,
        border=ft.border.all(1, "outline"),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.ExpansionTile(
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            controls=[ft.Column(controls=expansion_controls, horizontal_alignment=ft.CrossAxisAlignment.START)],
            controls_padding=20,
            bgcolor=ft.Colors.TRANSPARENT,
            collapsed_bgcolor=ft.Colors.TRANSPARENT,
            initially_expanded=is_expanded,
            on_change=on_tile_change
        )
    )

def _build_shell_command_for_items(items, with_wrapper=True):
    prefix = state.shell_cart_prefix.strip()
    suffix = state.shell_cart_suffix.strip()

    nix_pkgs_args = []
    for item in items:
        pkg = item['package']
        channel = item['channel']
        nix_pkgs_args.append(f"nixpkgs/{channel}#{pkg.get('package_pname')}")

    nix_args_str = " ".join(nix_pkgs_args)
    nix_cmd = f"nix shell {nix_args_str} --command bash --noprofile --norc"

    if with_wrapper:
        return f"{prefix} {nix_cmd} {suffix}".strip()
    else:
        return nix_cmd

def _launch_shell_dialog(display_cmd, title, page):
    cmd_list = shlex.split(display_cmd)
    
    output_text = ft.Text("Launching process...", font_family="monospace", size=12)
    
    content = ft.Container(
        width=500, height=150,
        content=ft.Column([
            ft.Text(f"Command: {display_cmd}", color=ft.Colors.BLUE_200, size=12, selectable=True), 
            ft.Divider(), 
            ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True)
        ])
    )
    
    close_func = [None]
    actions=[ft.TextButton("Close", on_click=lambda e: close_func[0]())]

    if controls_mod.show_glass_dialog:
            close_func[0] = controls_mod.show_glass_dialog(f"Launching {title}", content, actions)

    try:
        # Use pipes to capture output
        proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        
        # Wait briefly to check for immediate failure
        try:
            outs, errs = proc.communicate(timeout=0.5)
            # If we get here, process exited
            if proc.returncode != 0:
                err_msg = errs.decode('utf-8', errors='replace') if errs else "Unknown error"
                output_text.value = f"Process failed (Exit Code {proc.returncode}):\n{err_msg}"
            else:
                output_text.value = "Process finished immediately."
        except subprocess.TimeoutExpired:
            # Process is still running (good!)
            output_text.value = "Process started successfully."
        
        page.update()
    except Exception as ex:
        output_text.value = f"Error executing command:\n{str(ex)}"
        page.update()