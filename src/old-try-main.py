import flet as ft

# --- Mock Data ---
APPS_DATA = [
    {"name": "Nebula Notes", "category": "Productivity", "rating": "4.8", "icon": ft.Icons.EDIT_NOTE, "color": ft.Colors.PURPLE_400},
    {"name": "Zenith Fitness", "category": "Health", "rating": "4.9", "icon": ft.Icons.FITNESS_CENTER, "color": ft.Colors.GREEN_400},
    {"name": "Quantum Browser", "category": "Tools", "rating": "4.5", "icon": ft.Icons.PUBLIC, "color": ft.Colors.BLUE_400},
    {"name": "Pixel Painter", "category": "Design", "rating": "4.7", "icon": ft.Icons.PALETTE, "color": ft.Colors.ORANGE_400},
    {"name": "Echo Music", "category": "Entertainment", "rating": "4.6", "icon": ft.Icons.MUSIC_NOTE, "color": ft.Colors.PINK_400},
    {"name": "Cyber Guard", "category": "Security", "rating": "4.9", "icon": ft.Icons.SECURITY, "color": ft.Colors.CYAN_400},
]

SEARCH_SUGGESTIONS = ["Photo Editor", "VPN", "Games", "ToDo List", "Weather"]

# --- Custom Controls ---

class GlassContainer(ft.Container):
    """A helper container that applies the glassmorphic style."""
    def __init__(self, content, opacity=0.1, blur_sigma=10, border_radius=15, **kwargs):
        super().__init__(
            content=content,
            bgcolor=ft.Colors.with_opacity(opacity, ft.Colors.WHITE),
            blur=ft.Blur(blur_sigma, blur_sigma, ft.BlurTileMode.MIRROR),
            border_radius=border_radius,
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
            ),
            **kwargs
        )

class AppCard(GlassContainer):
    """A card displaying an individual app."""
    def __init__(self, app_data):
        self.app_data = app_data

        content = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(self.app_data["icon"], color=ft.Colors.WHITE, size=30),
                    width=60, height=60,
                    bgcolor=self.app_data["color"],
                    border_radius=12,
                    alignment=ft.alignment.center
                ),
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text(self.app_data["name"], weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.WHITE),
                        ft.Text(self.app_data["category"], size=12, color=ft.Colors.WHITE70),
                        ft.Row([
                            ft.Icon(ft.Icons.STAR, size=14, color=ft.Colors.AMBER),
                            ft.Text(self.app_data["rating"], size=12, color=ft.Colors.WHITE)
                        ], spacing=2)
                    ]
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    icon_color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE))
                )
            ],
        )
        super().__init__(content=content, padding=15, opacity=0.15)

class FeaturedCard(GlassContainer):
    """Large featured app card for the home screen."""
    def __init__(self):
        content = ft.Row(
            controls=[
                ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.ORANGE),
                            border_radius=5,
                            content=ft.Text("EDITOR'S CHOICE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_100)
                        ),
                        ft.Text("Cosmic Journey", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text("Explore the universe from your pocket.", size=14, color=ft.Colors.WHITE70),
                        ft.ElevatedButton(
                            "Install Now",
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.BLUE_600,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                        )
                    ]
                ),
                ft.Icon(ft.Icons.ROCKET_LAUNCH, size=100, color=ft.Colors.WHITE24)
            ]
        )
        super().__init__(content=content, height=200, opacity=0.2, padding=20)

# --- Main Application ---

def main(page: ft.Page):
    page.title = "Glassmorphic App Store"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 400
    page.window_height = 800

    # -- Views Content --

    # 1. Discover View
    def get_discover_view():
        return ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Text("Discover", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                FeaturedCard(),
                ft.Container(height=10),
                ft.Text("Trending Now", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Column(
                    spacing=10,
                    controls=[AppCard(app) for app in APPS_DATA[:3]]
                ),
                ft.Container(height=10),
                ft.Text("New Arrivals", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Column(
                    spacing=10,
                    controls=[AppCard(app) for app in APPS_DATA[3:]]
                ),
                ft.Container(height=80) # Spacer for bottom nav
            ]
        )

    # 2. Search View
    def get_search_view():
        return ft.Column(
            controls=[
                ft.Text("Search", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                GlassContainer(
                    opacity=0.15,
                    padding=ft.padding.only(left=15),
                    content=ft.TextField(
                        hint_text="Games, Apps, Books...",
                        border=ft.InputBorder.NONE,
                        hint_style=ft.TextStyle(color=ft.Colors.WHITE54),
                        text_style=ft.TextStyle(color=ft.Colors.WHITE),
                        prefix_icon=ft.Icons.SEARCH,
                        prefix_style=ft.TextStyle(color=ft.Colors.WHITE54)
                    )
                ),
                ft.Container(height=10),
                ft.Text("Suggestions", size=14, color=ft.Colors.WHITE54),
                ft.Row(
                    wrap=True,
                    controls=[
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                            border_radius=20,
                            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                            content=ft.Text(text, color=ft.Colors.WHITE70, size=12)
                        ) for text in SEARCH_SUGGESTIONS
                    ]
                ),
                ft.Container(height=20),
                ft.Text("Top Results", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Column(
                    scroll=ft.ScrollMode.HIDDEN,
                    expand=True,
                    spacing=10,
                    controls=[AppCard(app) for app in APPS_DATA]
                )
            ]
        )

    # 3. Settings View
    def get_settings_view():
        def setting_tile(icon, title, subtitle):
            return GlassContainer(
                opacity=0.1,
                padding=15,
                content=ft.Row([
                    ft.Icon(icon, color=ft.Colors.WHITE70),
                    ft.Column([
                        ft.Text(title, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text(subtitle, size=12, color=ft.Colors.WHITE54)
                    ], spacing=2, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ft.Colors.WHITE24)
                ])
            )

        return ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Text("Settings", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),

                # Profile Header
                GlassContainer(
                    opacity=0.2,
                    padding=20,
                    content=ft.Row([
                        ft.CircleAvatar(
                            content=ft.Icon(ft.Icons.PERSON),
                            bgcolor=ft.Colors.PURPLE_200,
                            radius=30
                        ),
                        ft.Column([
                            ft.Text("Alex Developer", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text("alex@example.com", color=ft.Colors.WHITE70)
                        ], spacing=2)
                    ])
                ),
                ft.Container(height=20),
                ft.Text("General", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                setting_tile(ft.Icons.WIFI, "Network Preferences", "Auto-update apps over Wi-Fi only"),
                setting_tile(ft.Icons.NOTIFICATIONS, "Notifications", "Manage app alerts and sounds"),
                setting_tile(ft.Icons.SECURITY, "Privacy & Security", "Fingerprint and password settings"),
                setting_tile(ft.Icons.LANGUAGE, "Language", "English (US)"),
            ]
        )

    # --- Navigation Logic ---

    content_area = ft.Container(
        expand=True,
        padding=20,
        content=get_discover_view()
    )

    # Custom NavBar to avoid 'NavigationDestination' missing error
    # and to provide a true glassmorphic look
    def build_custom_navbar(on_change):
        # We hold references to buttons to update their state
        buttons = []

        items = [
            (ft.Icons.EXPLORE_OUTLINED, ft.Icons.EXPLORE, "Discover"),
            (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Search"),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
        ]

        def handle_click(e):
            # Parse index from data
            idx = e.control.data
            # Update UI state
            for i, btn in enumerate(buttons):
                is_selected = (i == idx)
                btn.icon = items[i][1] if is_selected else items[i][0]
                btn.icon_color = ft.Colors.WHITE if is_selected else ft.Colors.WHITE54
                btn.update()

            # Trigger page change
            on_change(idx)

        for i, (icon_off, icon_on, label) in enumerate(items):
            btn = ft.IconButton(
                icon=icon_on if i == 0 else icon_off, # Default to first selected
                icon_color=ft.Colors.WHITE if i == 0 else ft.Colors.WHITE54,
                data=i,
                on_click=handle_click,
                tooltip=label
            )
            buttons.append(btn)

        return GlassContainer(
            opacity=0.15,
            border_radius=0, # Flat bottom
            blur_sigma=15,
            padding=10,
            margin=0,
            content=ft.Row(
                controls=buttons,
                alignment=ft.MainAxisAlignment.SPACE_AROUND
            )
        )

    def on_nav_change(idx):
        if idx == 0:
            content_area.content = get_discover_view()
        elif idx == 1:
            content_area.content = get_search_view()
        elif idx == 2:
            content_area.content = get_settings_view()
        content_area.update()

    nav_bar = build_custom_navbar(on_nav_change)

    # --- Layout Assembly ---

    background = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[
                "#2E1437", # Deep purple
                "#240C33",
                "#0F172A", # Dark blue/slate
            ]
        )
    )

    decorations = ft.Stack(
        controls=[
            ft.Container(
                width=300, height=300,
                bgcolor=ft.Colors.PURPLE_600,
                border_radius=150,
                top=-100, right=-50,
                blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR),
                opacity=0.4
            ),
            ft.Container(
                width=200, height=200,
                bgcolor=ft.Colors.BLUE_600,
                border_radius=100,
                bottom=100, left=-50,
                blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR),
                opacity=0.4
            ),
        ]
    )

    main_layout = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            content_area,
            nav_bar
        ]
    )

    page.add(
        ft.Stack(
            expand=True,
            controls=[
                background,
                decorations,
                main_layout
            ]
        )
    )

ft.app(target=main)
