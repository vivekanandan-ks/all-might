import json
import subprocess
import os
import re
import flet as ft
from controls import NixPackageCard
from state import state
from utils import execute_nix_search

def get_store_path_info(store_path):
    # Format: /nix/store/<hash>-<name>-<version>
    # or /nix/store/<hash>-<name>
    
    basename = os.path.basename(store_path)
    # Remove hash (32 chars) + dash
    if len(basename) > 33 and basename[32] == '-':
        rest = basename[33:]
    else:
        rest = basename

    # Heuristic to split name and version
    # Find the first dash followed by a digit
    match = re.search(r'-(\d)', rest)
    if match:
        idx = match.start()
        name = rest[:idx]
        version = rest[idx+1:]
    else:
        name = rest
        version = ""
    
    return name, version

def get_binaries(store_path):
    bin_path = os.path.join(store_path, "bin")
    if os.path.isdir(bin_path):
        try:
            return os.listdir(bin_path)
        except:
            return []
    return []

def extract_channel_from_url(url):
    # url examples:
    # flake:nixpkgs/nixos-unstable
    # flake:nixpkgs/nixos-24.11
    # flake:nixpkgs (implies default or master, we'll try default)
    # github:NixOS/nixpkgs/nixos-unstable
    
    if not url: return None
    
    # Try to match common patterns
    match = re.search(r'nixpkgs/(nixos-[\w\d\.]+)', url)
    if match:
        return match.group(1)
        
    if "flake:nixpkgs" in url and "/" not in url.split("flake:nixpkgs")[-1]:
         # No branch specified, could be anything. 
         # Let's assume nixos-unstable if we can't determine, or return None
         return "nixos-unstable"

    return None

def get_installed_packages():
    try:
        result = subprocess.run(
            ["nix", "profile", "list", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
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
            
            if not is_tracked:
                # Fallback: Check if tracked under any channel
                tracked_channel = state.get_tracked_channel(name)
                if tracked_channel:
                    is_tracked = True
                    channel = tracked_channel

            # Default/Fallback Data
            pkg_data = {
                "package_pname": name,
                "package_pversion": version,
                "package_description": f"Installed from {original_url}" if original_url else "Installed via nix profile",
                "package_homepage": [],
                "package_license_set": [],
                "package_programs": programs,
                "package_attr_set": attr_path if attr_path else "installed",
                "package_position": "", 
                "package_element_name": key, # Crucial for uninstall
                "is_installed": True,
                "is_all_might": is_tracked
            }
            
            if not is_tracked:
                # External app: "prefer no packages set" logic
                pkg_data["package_attr_set"] = "No package set"
            
            # Fetch rich details
            if state.installed_enrich_metadata and channel:
                try:
                    # Search for the exact package name
                    search_results = execute_nix_search(name, channel)
                    if search_results and "error" not in search_results[0]:
                        # Find exact match
                        best_match = None
                        for res in search_results:
                            if res.get("package_pname") == name:
                                best_match = res
                                break
                        
                        if best_match:
                            # Update with rich data, but keep local programs/version if needed?
                            # Usually we want the remote metadata (desc, license, homepage)
                            # But we should keep the installed version if possible, or display both?
                            # NixPackageCard uses 'package_pversion' from data. 
                            # Let's update metadata but maybe trust the search result version if it matches roughly?
                            # Actually, installed version is truth. Metadata is for info.
                            
                            pkg_data["package_description"] = best_match.get("package_description", pkg_data["package_description"])
                            pkg_data["package_homepage"] = best_match.get("package_homepage", [])
                            pkg_data["package_license_set"] = best_match.get("package_license_set", [])
                            pkg_data["package_position"] = best_match.get("package_position", "")
                            # If search result has an attr set and we don't (or it's better), use it
                            if not pkg_data["package_attr_set"] or pkg_data["package_attr_set"] == "installed":
                                pkg_data["package_attr_set"] = best_match.get("package_attr_set", "")

                except Exception as e:
                    print(f"Failed to enrich package {name}: {e}")
            
            packages.append({"pkg": pkg_data, "channel": channel})
            
        return packages
    except Exception as e:
        print(f"Error fetching installed packages: {e}")
        return []

def get_installed_view(page, on_cart_change_callback, show_toast_callback, refresh_callback=None):
    packages = get_installed_packages()
    
    update_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    
    if not packages:
        update_list.controls.append(
            ft.Container(
                content=ft.Text("No packages found in nix profile.", color="onSurface"),
                alignment=ft.alignment.center,
                padding=20
            )
        )
    else:
        for item in packages:
            pkg_data = item['pkg']
            channel = item['channel']
            
            card = NixPackageCard(
                package_data=pkg_data,
                page_ref=page,
                initial_channel=channel,
                on_cart_change=on_cart_change_callback,
                is_cart_view=False,
                show_toast_callback=show_toast_callback,
                on_menu_open=None
            )
            update_list.controls.append(card)

    header_controls = [
        ft.Text("Installed Apps", size=24, weight=ft.FontWeight.BOLD, color="onSurface")
    ]
    if refresh_callback:
        header_controls.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Installed Status", on_click=refresh_callback))

    return ft.Container(
        expand=True,
        padding=20,
        content=ft.Column(
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=header_controls),
                ft.Divider(),
                ft.Container(
                    expand=True,
                    content=update_list
                ),
                ft.Container(height=100) # Spacer for bottom nav
            ]
        )
    )
