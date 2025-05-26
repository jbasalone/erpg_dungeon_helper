# Epic RPG Discord Dungeon Helper

A **Discord bot** for automatically solving and assisting with high-level Epic RPG dungeons (D10–D15), with advanced logic for D13, D14, and D15.  
Supports both classic `rpg dungeon` message-based runs and `/dungeon` slash commands.

---

## Features

- 🐉 **D13 Auto-Solver:**  
  - Answers all D13 "Ultra-Omega Dragon" questions automatically.
  - Detects current dungeon phase and picks the right answer type (`correct`, `not_so_wrong`, or `wrong`).
  - Handles mistakes and recovers state automatically, always giving the correct next move.

- 🧩 **D14 Solver:**  
  - Integrates with an external binary for optimal path-finding (Linux and Windows supported).
  - Provides best HP solution, brown-tile fallback, and interactive Discord UI buttons.

- ⏳ **D15 & D15.2 Support:**  
  - External solver integration for Time Dragon dungeons, including board state and move simulation.
  - Verifies solver outputs, can retry for valid solutions, and applies move effects for full simulation.

- ⚔️ **General Features:**
  - **Multi-dungeon:** Supports D10–D15 helpers, with flexible channel-based enable/disable.
  - **Slash Command Compatible:** Seamless support for both classic and slash dungeons.
  - **Smart Deduplication:** No duplicate answers or repeated moves.
  - **Mistake Recovery:** Bot always recovers and recalculates from the current game state.
  - **Configurable:** Per-dungeon and per-channel toggles in `settings.py`.

---

## Getting Started

### Prerequisites

- Python 3.9+
- [discord.py](https://github.com/Rapptz/discord.py) (tested on v2.x)
- Epic RPG Discord bot
- Access to compile/run C++ or Rust binaries (for D14/D15 solvers)
- Linux or Windows OS

### Setup

1. **Clone this repository:**
    ```bash
    git clone https://github.com/yourusername/epic-rpg-dungeon-helper.git
    cd epic-rpg-dungeon-helper
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure your settings:**
    - Copy `settings_example.py` to `settings.py` and edit your bot token, allowed channels, and other config as needed.
    - Add your Discord bot credentials and set channel IDs for each dungeon helper.

4. **(Optional) Build/Download Solvers:**
    - For D14/D15: Place compiled solver binaries in `dungeon_solvers/D14/` and `dungeon_solvers/D15/` as required.

5. **Run the bot:**
    ```bash
    python main.py
    ```

---

## Technical Overview

### Main Components

- `main.py` – Event loop, message & embed handlers, command router.
- `dung_helpers.py` – Dungeon logic for D13–D15; action selection, state, solver interface.
- `settings.py` – Bot config: IDs, allowed channels, dungeon helper state.
- `utils_bot.py` – Helper utilities: dungeon detection, permissions, bot interaction.
- `dungeon_solvers/` – External binaries for advanced dungeon pathfinding.

### D13 Helper Logic

- **Game Phases:**  
  D13 is divided into 4 main steps, auto-detected from board state (`room_number`, `dragon_room`).
- **Answer Selection:**  
  The bot parses the question/answers and picks the right answer using logic from `get_d13_action` and `get_answer`.
- **Recovery:**  
  If the user makes a mistake, the bot recalculates phase from the current embed, and shows a friendly message.
- **Deduplication:**  
  The bot ensures each state is only answered once per room/question combo.

### Other Dungeons

- **D14 & D15**  
  Call external binaries to compute optimal moves, parse board state, and respond via Discord.
- **D15.2**  
  Handles special phase 2 mechanics and advanced move simulation.

---

## Usage

- Start a dungeon as usual (`rpg dungeon` or `/dungeon`).
- The bot will detect D13–D15 dungeons and post the correct moves in the configured channel.
- For D13: The bot will always recover from mistakes, show which move to pick, and increment turn count.
- For D14/D15: Interactive helpers, external solvers, and Discord UI buttons are available.

---

## Configuration

- **Per-dungeon channel enable:**  
  In `settings.py`, edit the `DUNGEON13_HELPERS`, `DUNGEON14_HELPERS`, etc., to control which channels each helper is active in.

- **Slash command compatibility:**  
  The bot auto-detects whether the run is classic or slash and responds accordingly (edit in-place or send a new message).

---

## Contribution

Contributions, bug reports, and feature requests are welcome!

- Fork the repository
- Create a branch (`git checkout -b feature/my-feature`)
- Commit your changes
- Push to the branch (`git push origin feature/my-feature`)
- Open a Pull Request

---

## License

MIT License (see [LICENSE](LICENSE) for details)

---

## Acknowledgements

- [Epic RPG](https://discord.gg/epic-rpg) (the original game)
- Open-source contributors on GitHub
- The Epic RPG helper community
- Original Solvers from Discord Users: @necromancer23 @557841939375063068

---

## FAQ

**Q: What happens if I make a mistake in D13?**  
A: The bot automatically recalculates the correct step and continues from your current state.

**Q: Do I need to recompile the solvers?**  
A: Only if you're on a new platform or want to update for a new Epic RPG mechanic.

**Q: Can I use this for D10–D12?**  
A: Yes, basic helpers are included for lower dungeons.

---

## Screenshots


---

Happy dungeoning!
