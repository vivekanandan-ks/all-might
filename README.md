# About this project: all-might
This project is an attempt to bring a user friendly and powerful GUI for nixpkgs.
Project planned to work Cross platform for All platforms where Nix works like Most Linux distros, Mac and Android(possibly with the AVF efforts from Android 16 onwards?).

# Why nixpkgs?
Too many reasons. 
* For starters: 1.2 millions packages in nixpkgs and that's fresh too. And u have option to use it as roling release branch or stable one or BOTH. Cool right?
* For intermediate: nixpkgs is the huge attempt at building an universal package manager and build system which is also functional, declarative and thus reproducible, reliable etc
* For Advanced: This will help u understand how awesome is nix and it's ecosystem.
For Others: Coz it's made with Nix

# Why not flatpaks, Snaps, AppImages?
All those are cool, but sometimes they have:
* Large Runtimes
* Performance Overhead
* Centralized and Proprietary Store
* etc
But even if u are someone who are sometimes not mesmerized by nixpkgs and want to install flatpaks too declaratively? Possibly a plan to include flatpak support too, but have to be decided later on this. Coz somemight like flatpaks to be managed separately with another app store like Easy Flatpak etc. Let's discuss on this.

# What does all-might do different from other app stores?
* U can choose to install apps from both rolling and stable branch together :-). Again Cool right?

# Features planned
* Choosing apps from stable or unstable repo branches (probably even old repo branches)
* Optional Integration with git, so that ur whole apps list are backed up to ur git remote and thus alowing u to restore ur apps setup with just few commands
* Integration with ur existing home manager or nix configuration
* Support for All linux distros(which supports nix), Mac (and Android with AVF depending upon the progress in Android)
* Clean uninstall of all apps managed by all-might
* Easy rollback if something breaks after installing some apps
* Optional Gentoo like local build without binary. Why? No reason. Just for source repo model fans.
* Flatpak apps declaratively (yet to be decided)
* Optional Auto update of apps
* Optional Auto refresh of repos

# Why the name all-might
IUKUK (will reveal the detailed reason later)

# Tech Stack
I want the project to be cross platformic and I'm little familiar with python. So I'm using the flet framework for this as for now. Who knows some crazy person will do a lightweight or rust rewrite and submit a PR and it's more than welcome. I love options, so probably different UI frameworks can also be done in parallel and users can have option to install whatever the framework they like, so that project grows with unified efforts than diverging. Of course with nix it's greatly helpful to do those.

# Roadmap
* A Basic working app
* Features getting added one by one

The README is also WIP. So please feel free to suggest features / anything.
