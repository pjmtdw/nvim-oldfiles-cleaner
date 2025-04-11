# What is this for?

I frequently use `oldfiles` feature of Neovim. But I noticed that some files such as deleted file remains in the `oldfiles` and I want to delete it.

This script removes some items from `oldfiles` in Neovim by modifing the Shada file, which Neovim uses to fill `oldfiles` at startup.

# Features

- Remove from `oldfiles` that files do not exist in filesystem.
- Remove from `oldfiles` using regular expressions.
- Remove from `oldfiles` by selecting from the `fzf` command.

# Requirements

- Neovim
- Python >= 3.9
- fzf (Optional)

# Install

This is a small Python script that only uses the standard library, so just download [nvim-oldfiles-cleaner.py](./nvim-oldfiles-cleaner.py) and run it.

# Usage

List oldfiles

```bash
$ ./nvim-oldfiles-cleaner.py --list
```

Remove oldfiles that do not exist in filesystem.
```bash
$ ./nvim-oldfiles-cleaner.py --gone
```

Remove oldfiles using regular expressions.
```bash
$ ./nvim-oldfiles-cleaner.py '^/tmp/' '\.bak$'
```

Remove oldfiles by selecting from the `fzf` command.
```bash
$./nvim-oldfiles-cleaner.py --fzf
```

# Caveats

- This script removes jumps, marks, and change history of the target from Shada file.
- The original Shada file is backed up to `~/.local/state/nvim/shada/main.shada.old` before writing it. If something goes wrong, restore it from this location.
- This script is only tested on Linux and macOS, so I don't know whether it works in Windows or not.

# Open Problems

- Using Neovim for reading/writing Shada files is quite slow. Can we speed it up using the msgpack library?
- Can we write this script as pure Neovim plugin?
