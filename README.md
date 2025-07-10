# Epic RPG Discord Dungeon Helper

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-v2.x-blueviolet)](https://github.com/Rapptz/discord.py)
[![License](https://img.shields.io/github/license/jbasalone/epic-rpg-dungeon-helper.svg?style=flat)](LICENSE)
[![Issues](https://img.shields.io/github/issues/jbasalone/epic-rpg-dungeon-helper.svg)](https://github.com/jbasalone/epic-rpg-dungeon-helper/issues)
[![Stars](https://img.shields.io/github/stars/jbasalone/epic-rpg-dungeon-helper.svg?style=social)](https://github.com/jbasalone/epic-rpg-dungeon-helper/stargazers)

A **feature-rich Discord bot** for automatically solving and assisting with high-level Epic RPG dungeons (D10–D15), with advanced logic for D13, D14, and D15.  
Supports both classic `rpg dungeon` text commands and `/dungeon` slash commands. Now with improved mistake recovery, interactive Discord UI, and robust anti-rate-limit handling.

---

## Features

- 🐉 **Full D10–D15 Auto-Assist:**
    - Solves all D10–D15 dungeons, including unique logic for each.
    - **D13:** Instantly answers all Ultra-Omega Dragon questions, handles all "phase" transitions, and always recovers state.
    - **D14:** Calls an external binary (Windows & Linux supported) for true optimal pathfinding, with brown-tile fallback and Discord UI buttons.
    - **D15/D15.2:** Time Dragon solver with move simulation, external binary, and safety checks.
- ⚡ **Mistake Proof:**
    - The bot tracks dungeon state, deduplicates answers, and always recalculates after user errors or manual moves.
- 🔄 **Smart Rate-Limit & Edit Handling:**
    - Built-in debounce, cooldowns, and retry logic for Discord rate limits and Epic RPG's edit-driven embeds.
- 🆕 **Interactive UI:**
    - Modern Discord UI components for "go to brown tile," solution confirmation, and HP warnings.
- 🎛️ **Highly Configurable:**
    - Per-dungeon and per-channel toggles, slash/classic autodetection, easy setup in `settings.py`.
- 🛡️ **Persistent State (on restart):**
    - Dungeon helper data is cached per channel, so helpers recover after a bot reboot.
- 🔍 **Debug & Recovery Tools:**
    - Extensive logging, dev commands for clearing helper state or rate-limit recovery.

---

## Getting Started

### Prerequisites

- Python 3.9+ (tested with 3.9–3.12)
- [discord.py v2.x](https://github.com/Rapptz/discord.py)
- The Epic RPG Discord bot in your server
- Ability to compile/run external solver binaries (C++ or Rust, for D14/D15)
- Linux or Windows OS

### Setup

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/epic-rpg-dungeon-helper.git
    cd epic-rpg-dungeon-helper
    ```

2. **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure your bot:**
    - Copy `settings_example.py` to `settings.py`.
    - Edit your Discord bot token, allowed channel IDs, and any helper toggles needed.

4. **Solvers for D14 & D15:**
    - Build or download the external solver binaries for your OS.
    - Place them in `dungeon_solvers/D14/` and `dungeon_solvers/D15/` folders.

5. **Run the bot:**
    ```bash
    python main.py
    ```

---

## Technical Overview

### Main Components

- `main.py` – Bot event loop, message & edit handlers, command registration.
- `handlers/` – Each dungeon (D10–D15) has its own logic, state tracking, and embed parsing.
- `dung_helpers.py` – Advanced logic, answer parsing, and solver interface.
- `settings.py` – Global config, IDs, helper state.
- `utils_*.py` – Helper modules: channel permissions, cache, rate limit handling, safe_send utilities.
- `dungeon_solvers/` – External binaries for D14/D15 pathfinding.

### Dungeon Helper Logic

- **Auto-Detection:**  
  The bot uses embed parsing and message context to determine which dungeon and phase is active.
- **Error Recovery:**  
  If the bot is restarted or the user makes an incorrect move, the bot resynchronizes with the current dungeon state.
- **Deduplication:**  
  Only one helper output per move/phase; repeated events are ignored.
- **Victory/Completion Handling:**  
  The bot automatically clears and resets helper state on victory or channel wipe.

---

## Usage

- **Start a dungeon as usual** (`rpg dungeon` or `/dungeon`).
- The bot will detect and post the correct moves for D10–D15 in the configured channels.
- For D13–D15:
    - Full recovery if you make mistakes or do manual moves.
    - Interactive Discord UI for brown-tile fallback or solution confirmations (D14).
    - HP and safety warnings if your stats are low.

---

## Configuration

- **Per-dungeon, per-channel enable:**  
  Configure allowed channels and dungeon toggles in `settings.py`.
- **Slash command support:**  
  Classic and slash dungeons are automatically detected and handled.
- **Advanced (optional):**
    - Rate-limit/cooldown values
    - Custom HP warnings
    - Dev/test command registration for live debugging

---

## Contribution

All contributions, bug reports, and feature requests are welcome!

- Fork the repository.
- Create a feature branch (`git checkout -b feature/my-feature`).
- Make your changes, push (`git push origin feature/my-feature`).
- Open a Pull Request.

---

## License

MIT License (see [LICENSE](LICENSE) for details)

---

## Acknowledgements

- [Epic RPG](https://discord.gg/epic-rpg)
- Discord.py maintainers and open-source contributors
- Special thanks: @necromancer23, @557841939375063068

---

## FAQ

**Q: Does the bot recover after a Discord or bot restart?**  
A: Yes! Helper state is tracked per channel and re-synced on the next move or embed.

**Q: What if I get rate-limited?**  
A: The bot will retry sending messages, respect Discord rate limits, and recover state if interrupted.

**Q: Do I have to compile the solvers?**  
A: You only need to build the external binaries for D14/D15 if your platform changes or a solver update is needed.

**Q: Can I use this bot for D10–D12?**  
A: Yes—basic helpers are included for all dungeons, with advanced logic for D13+.

---

## Screenshots

*(Insert screenshots here to showcase the bot in action!)*

---

Happy dungeoning & good luck with your dragons! 🐲