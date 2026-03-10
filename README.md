# ACE-Step Installer

> One-click install. Zero configuration. Full control.

Built because a YouTube tutorial shipped a steering wheel with no car attached, and thousands of people crashed trying to figure out the rest. This package gives you the complete vehicle.

---

## Package Contents

```
ACE-Step-Installer/
|-- INSTALL.bat                          <-- Double-click. That's the whole instruction.
|-- Advanced_Install.bat                 <-- Don't.
|-- installer/
|   |-- ACE-Step-Installer.ps1           <-- The actual installer (PowerShell)
|   +-- launcher.py                      <-- Desktop launcher with system tray + heartbeat
|-- webui/
|   +-- Uni404x64_s-2step-webui_v8_.html <-- Custom WebUI (single-file, no build step)
|-- README.md                            <-- You are here
+-- LICENSE
```

> **Note:** `Advanced_Install.bat` is a rickroll. There is no advanced install. If you're reading this, congratulations -- you read the README. The people who didn't are currently watching ASCII Rick Astley perform in a terminal window.

> **SECURITY DISCLAIMER:** `Advanced_Install.bat` contains a harmless Rickroll prank script. Automated security scanners and local antivirus software *will* flag the `iex` web-request behavior as a false positive because it structurally mimics a remote code dropper. There is no actual malware or destructive payload. Review the batch logic directly if you have concerns.

---

## What This Is

A complete installer + custom WebUI + desktop launcher for [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5), the open-source AI music generation model by ACE Studio & StepFun.

**The Installer** handles UV, Git, repo cloning, dependency resolution, model downloads (with resume support), launcher creation, and desktop shortcuts. One click.

**The WebUI** is a single-file HTML interface with proximity-based slide-out panels, dual animated backgrounds, full theme customization, a BYOB (Bring Your Own Bot) system for cross-AI configuration, and an IndexedDB-backed song library. No frameworks, no build tools, no npm. Just drop it in a folder and open it.

**The Launcher** is a Python/CustomTkinter desktop app with one-button launch, system tray minimization, heartbeat-based auto-shutdown, orphan process cleanup, and multi-UI support.

---

## Quick Start

**Double-click `INSTALL.bat`**

That's it. It auto-elevates to admin and handles everything.

### Install Options

| Option | How |
|---|---|
| Basic install | Just run `INSTALL.bat` |
| Pre-downloaded models | Add `-ModelsSource "C:\path\to\checkpoints"` to the bat |
| Custom install location | Add `-InstallPath "D:\AI\ACE-Step"` to the bat |

### After Install

You get three launchers in your install directory:

- **Launch_WebUI.bat** -- Starts API + opens the custom WebUI. This is the one you want.
- **Launch_API.bat** -- API server only (port 8001). For custom integrations.
- **Launch_Gradio.bat** -- Official Gradio UI (port 7860). Full feature set.

---

## WebUI Features (V8 -- Current Release)

### Core Interface
- **Proximity panel system** -- Four slide-out panels (Library, Settings, Customize, Output) that peek on mouse proximity and pin on click
- **Workspace push logic** -- Pinned panels shift the center workspace to avoid overlap
- **Dual animated backgrounds** -- Neural Net constellation and Matrix Rain, independently configurable
- **Full theme engine** -- 10 built-in presets + BYOB custom themes via any AI

### Generation
- **Multi-mode generation** -- Text-to-Music, Repaint (inpainting with waveform region selection), Cover, and Extend
- **Tag cloud system** -- Foldable categories, right-click context menus for move/delete/favorite, custom categories and tags
- **BYOB (Bring Your Own Bot)** -- Copy a structured prompt, paste it into any AI (Claude, GPT, Gemini, Grok, local models), get back a JSON config that auto-populates all generation parameters
- **Auto-play toggle** -- Control whether new generations auto-play or wait for manual playback
- **Progressive trash talk** -- The Generate button develops strong opinions about your productivity over extended sessions

### Settings & Control
- **Full parameter access** -- Duration, BPM, Seed, Infer Steps, Guidance Scale, LM CFG Scale, LM Temperature, LM Top-P, Audio Format, Language, Key, Time Signature
- **Dice randomization buttons** -- One-click randomize on Seed, Duration, BPM
- **Scroll wheel adjustment** -- Mouse wheel on any number input. Hold Shift for 10x step size.
- **Ctrl+Enter to generate** -- Keyboard-first workflow support

### Library
- **IndexedDB-backed storage** -- No 5MB localStorage ceiling. Holds 2000+ entries.
- **Full parameter recall** -- Click any previous generation to see every setting that produced it
- **Copy Prompt / Reapply Settings** -- Reload any previous generation's configuration in one click
- **Listened tracking** -- Previously played tracks dim for easy visual scanning
- **Star favorites** -- Pin your best generations without accidentally collapsing the panel

### Launcher (V4)
- **Heartbeat watchdog** -- Browser pings launcher; API server auto-stops when all tabs close
- **Generation-safe shutdown** -- Will not terminate the API mid-generation, even if the heartbeat lapses
- **Orphan process cleanup** -- Detects and kills stale acestep-api processes from crashed sessions
- **Multi-UI support** -- Drop any `.html` file in `/webui/` and it opens automatically on launch
- **Cross-platform foundations** -- Platform detection, Unix-compatible subprocess management, PyTorch device routing (CUDA / Apple MPS / CPU fallback)

---

## Roadmap

### V8 -- "The Bulldozer" (Current)
*Shipped. Functional. In the webui folder right now.*

22 features implemented. All API parameters verified against the latest upstream ACE-Step 1.5 codebase (including the modular API refactor and new job pipeline).

---

### V9 -- "The Architect"
*Target: 7 days | Scheduled ceiling: 30 days*

#### Immersive Audio
- **Defrost Mode** -- Full-screen immersion. All UI fades to transparent, interactions disable, and the background visualizer runs at maximum intensity while you listen. Re-enables on song completion or Escape. *(Concept by Gemini, implementation by Uni404x64.)*
- **Audio playback isolation** -- Library playback operates independently from generation output. New generations never interrupt a Library track unless Auto-Play is explicitly on.
- **Playhead stability pass** -- Investigate and resolve the suspected pin-state/playhead tracking conflict.

#### AI Identity System
- **BYOB Signatures** -- AI-generated tags and themes carry a persistent identifier. Visual differentiation at a glance: which AI suggested which tags, which AI built which theme. Identifiers are independent of theme selection and persist across sessions.
- **Identifier-aware Library** -- Filter and visually trace library entries by the AI that configured them.

#### Advanced Backgrounds
- **Dedicated customization dropdown** -- Consolidated speed, intensity, and color dynamics for both visualizer modes under an expandable Advanced section.
- **Particle color dynamics** -- Slider controlling how many colors the constellation nodes cycle through.
- **Connection destabilization (experimental)** -- Randomized waveform-style connections between constellation nodes. Targeting controlled visual chaos without performance degradation. Ships only if stable.

#### Layout & Panels
- **Resizable panels** -- Drag handles on the inner edges of Library and Output panels for horizontal width adjustment.

#### Network & Backend
- **Remote generation** -- Connect to a remote ACE-Step API instance over the network. Use a friend's hardware for generations that exceed local VRAM limits. Caddy integration for secure tunneling.
- **VRAM-aware model management** -- Dynamic load/unload of models from VRAM, using system RAM as a staging area for constrained hardware.
- **New upstream API parameters** -- Expose `infer_method` (ODE/SDE), `shift`, `timesteps`, `cover_noise_strength`, multi-model selection, and sample mode.
- **Full cross-platform launcher** -- Complete Linux and macOS support for all launcher features.

---

## Requirements

- Windows 10/11 (Linux/Mac: partial launcher support; WebUI works everywhere)
- Internet connection (first-time setup only)
- ~20GB free disk space (15GB models, 5GB code/deps)
- Git (installer prompts if missing)
- Python is NOT required -- UV handles the entire environment

## Troubleshooting

**Nothing happens when I double-click INSTALL.bat**
Make sure you extracted ALL files from the zip. Try right-click, Run as Administrator.

**"UV not found" after install**
Restart your terminal/PowerShell after the installer finishes.

**Models not downloading**
Your firewall might be blocking HuggingFace. The installer will skip the download and models will auto-download on first launch instead.

**First launch takes a long time**
That's normal. Models load into VRAM on first run. Subsequent launches are faster.

## Credits

## Credits & License
* **ACE-Step 1.5:** ACE Studio & StepFun (MIT License)
* **Installer, WebUI, Launcher:** Uni404x64 (GPL-3.0)
* **Motivation:** Built out of sheer spite for broken, generic tutorials that ship steering wheels with no cars attached.
* **Concepts:** Gemini Oddly enough in Google Docs I don't even use the Google Docs I was just fucking around and then Gemini in the edit mode I started a conversation with because it's not supposed to be used like that and it went surprisingly hilariously well it was amazing and then Gemini came up with the concept which will be implemented later with slight variations from original concept because it just didn't make any sense but the idea behind it did in a certain scenario so she came up with what will be called (Defrost Mode) a full-screen immersive mode where the UI fades away and the background visualizer runs at max intensity while you listen to your generation. It's meant to be a vibe mode for just enjoying the music without distractions, and it re-enables on song completion or if you hit Escape. I thought it was a brilliant idea and I will make it happen.

*Built from a dead motherboard and six months of self-taught systems architecture. If the installer works, the 24-hour nightmare is over.*

## License

GPL-3.0. Free to use, modify, and distribute -- but any derivative work must also be open-source under the same license. That's the deal.

The ACE-Step model itself is MIT licensed. This installer, WebUI, and launcher are GPL-3.0.

--- 

Congratulations on not adding to the body count number of the Rick roll however we both know you're going to go click that button anyway and watch the ASCII Rick Astley perform in a terminal window. It's okay, I think have brain damage from how many times I clicked it.. So I won't tell anybody if you don't.. ❤️