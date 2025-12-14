import json
import subprocess
import os
import re
import threading
import flet as ft
from controls import NixPackageCard
from state import state


def get_store_path_info(store_path):
    # Format: /nix/store/<hash>-<name>-<version>
    # or /nix/store/<hash>-<name>

    basename = os.path.basename(store_path)
    # Remove hash (32 chars) + dash
    if len(basename) > 33 and basename[32] == "-":
        rest = basename[33:]
    else:
        rest = basename

    # Heuristic to split name and version
    # Find the first dash followed by a digit
    match = re.search(r"-(\d)", rest)
    if match:
        idx = match.start()
        name = rest[:idx]
        version = rest[idx + 1 :]
    else:
        name = rest
        version = ""

    return name, version


def get_binaries(store_path):
    bin_path = os.path.join(store_path, "bin")
    if os.path.isdir(bin_path):
        try:
            return os.listdir(bin_path)
        except Exception:
            return []
    return []


def extract_channel_from_url(url):
    # url examples:
    # flake:nixpkgs/nixos-unstable
    # flake:nixpkgs/nixos-24.11
    # flake:nixpkgs (implies default or master, we'll try default)
    # github:NixOS/nixpkgs/nixos-unstable

    if not url:
        return None

    # Try to match common patterns
    match = re.search(r"nixpkgs/(nixos-[\w\d\.]+)", url)
    if match:
        return match.group(1)

    if "flake:nixpkgs" in url and "/" not in url.split("flake:nixpkgs")[-1]:
        # No branch specified, could be anything.
        # Let's assume nixos-unstable if we can't determine, or return None
        return "nixos-unstable"

    return None


def extract_attr_set(attr_path):
    if not attr_path:
        return "installed"
    parts = attr_path.split(".")
    # Expected: legacyPackages.<system>.<attrset>.<pname> OR legacyPackages.<system>.<pname>

    if len(parts) > 2 and parts[0] == "legacyPackages":
        # Remove legacyPackages and system
        relevant = parts[2:]  # Strip legacyPackages and system

        if len(relevant) > 1:
            # e.g. haskellPackages.hello -> attrset is haskellPackages
            # e.g. kdePackages.kcalc -> attrset is kdePackages
            # We return the first part of the remainder as the set name
            return relevant[0]
        else:
            # e.g. hello -> attrset is standard (nixpkgs)
            return "No package set"

    return attr_path  # Fallback


def get_installed_packages():
    try:
        result = subprocess.run(
            ["nix", "profile", "list", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        elements = data.get("elements", {})

        packages = []
        for key, info in elements.items():
            store_paths = info.get("storePaths", [])
            if not store_paths:
                continue

            store_path = store_paths[0]
            name, version = get_store_path_info(store_path)

            if name == "home-manager-path":
                continue

            # Try to get programs
            programs = get_binaries(store_path)

            attr_path = info.get("attrPath", "")
            original_url = info.get("originalUrl", "")

            # Determine channel
            channel = extract_channel_from_url(original_url) or state.default_channel

            # Check tracking
            is_tracked = state.is_tracked(name, channel)
            tracked_data = None

            if is_tracked:
                tracked_data = state.tracked_installs.get(
                    state._get_track_key(name, channel)
                )

            if not is_tracked:
                # Fallback: Check if tracked under any channel
                tracked_channel = state.get_tracked_channel(name)
                if tracked_channel:
                    is_tracked = True
                    channel = tracked_channel
                    tracked_data = state.tracked_installs.get(
                        state._get_track_key(name, tracked_channel)
                    )

            # Default/Fallback Data
            clean_attr_set = extract_attr_set(attr_path)

            pkg_data = {
                "package_pname": name,
                "package_pversion": version,
                "package_description": f"Installed from {original_url}"
                if original_url
                else "Installed via nix profile",
                "package_homepage": [],
                "package_license_set": [],
                "package_programs": programs,
                "package_attr_set": clean_attr_set,
                "package_position": "",
                "package_element_name": key,  # Crucial for uninstall
                "is_installed": True,
                "is_all_might": is_tracked,
            }

            if is_tracked and tracked_data:
                # Use stored metadata for All-Might installed apps
                if tracked_data.get("attr_name"):
                    # Use the tracked attr_name for display
                    # We might need to override the name variable or just pass it in pkg_data
                    # But NixPackageCard uses "package_pname" and calculates "attr_name" from "package_attr_name"
                    # So we should set package_attr_name
                    pkg_data["package_attr_name"] = tracked_data["attr_name"]

                if tracked_data.get("description"):
                    pkg_data["package_description"] = tracked_data["description"]
                if tracked_data.get("homepage"):
                    pkg_data["package_homepage"] = tracked_data["homepage"]
                if tracked_data.get("license"):
                    pkg_data["package_license_set"] = tracked_data["license"]
                if tracked_data.get("programs"):
                    pkg_data["package_programs"] = tracked_data["programs"]
                if tracked_data.get("source"):
                    src = tracked_data["source"]
                    if "blob/master/" in src:
                        pkg_data["package_position"] = src.split("blob/master/")[1]
            else:
                # External app
                pkg_data["package_attr_set"] = ""

                # Description becomes the clean URL for display as chip
                clean_desc = (
                    original_url.replace("flake:", "")
                    if original_url
                    else "Unknown source"
                )
                pkg_data["package_description"] = clean_desc

                # For external apps, we just show the attrPath from nix profile as the "attr_name"
                # If attr_path is available, clean it up (get last part)
                if attr_path:
                    parts = attr_path.split(".")
                    pkg_data["package_attr_name"] = parts[-1] if parts else attr_path
                else:
                    pkg_data["package_attr_name"] = name  # Fallback to pname

            packages.append({"pkg": pkg_data, "channel": channel})

        return packages
    except Exception as e:
        print(f"Error fetching installed packages: {e}")
        return []


def get_installed_view(
    page,
    on_cart_change_callback,
    show_toast_callback,
    show_dialog_callback=None,
    refresh_callback=None,
):
    # Filter State
    filter_state = {"selected": "all-might"}  # default to all-might

    def update_view():
        packages = get_installed_packages()

        count_all = len(packages)
        count_all_might = len([p for p in packages if p["pkg"]["is_all_might"]])
        count_external = count_all - count_all_might

        # Update chip labels (order: All-Might, External, All)
        filter_row.controls[
            0
        ].label.value = f"Installed by All-Might ({count_all_might})"
        filter_row.controls[1].label.value = f"Externally Installed ({count_external})"
        filter_row.controls[2].label.value = f"All ({count_all})"

        if filter_row.page:
            filter_row.update()

        filtered_packages = []

        if filter_state["selected"] == "all-might":
            filtered_packages = [p for p in packages if p["pkg"]["is_all_might"]]
        elif filter_state["selected"] == "external":
            filtered_packages = [p for p in packages if not p["pkg"]["is_all_might"]]
        else:  # all
            filtered_packages = packages

        update_list.controls.clear()

        if not filtered_packages:
            update_list.controls.append(
                ft.Container(
                    content=ft.Text("No packages found.", color="onSurface"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            for item in filtered_packages:
                pkg_data = item["pkg"]
                channel = item["channel"]

                card = NixPackageCard(
                    package_data=pkg_data,
                    page_ref=page,
                    initial_channel=channel,
                    on_cart_change=on_cart_change_callback,
                    is_cart_view=False,
                    show_toast_callback=show_toast_callback,
                    on_menu_open=None,
                    on_install_change=lambda: update_view(),
                    show_dialog_callback=show_dialog_callback,
                )
                update_list.controls.append(card)

        if update_list.page:
            update_list.update()

    update_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    def on_filter_change(e):
        filter_state["selected"] = e.control.data
        for control in filter_row.controls:
            control.selected = control.data == filter_state["selected"]
        filter_row.update()
        update_view()

    filter_row = ft.Row(
        controls=[
            ft.Chip(
                label=ft.Text("Installed by All-Might"),
                data="all-might",
                selected=True,
                on_select=on_filter_change,
            ),
            ft.Chip(
                label=ft.Text("Externally Installed"),
                data="external",
                selected=False,
                on_select=on_filter_change,
            ),
            ft.Chip(
                label=ft.Text("All"),
                data="all",
                selected=False,
                on_select=on_filter_change,
            ),
        ]
    )

    header_controls = [
        ft.Text("Installed Apps", size=24, weight=ft.FontWeight.BOLD, color="onSurface")
    ]
    if refresh_callback and state.show_refresh_button:
        header_controls.append(
            ft.IconButton(
                ft.Icons.REFRESH,
                tooltip="Refresh Installed Status",
                on_click=refresh_callback,
            )
        )

    # Initial Load
    # We delay the initial load slightly to allow the UI to render the skeleton first if needed,
    # but here we just call it.

    threading.Thread(target=update_view, daemon=True).start()

    return ft.Container(
        expand=True,
        padding=20,
        content=ft.Column(
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=header_controls,
                ),
                ft.Divider(),
                filter_row,
                ft.Container(height=10),
                ft.Container(expand=True, content=update_list),
                ft.Container(height=100),  # Spacer for bottom nav
            ]
        ),
    )
