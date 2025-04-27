# What is this for?

The `oldfiles` feature in NeoVim is a list of files you have recently opened and is commonly used in some plugins, such as:
- `oldfiles` in [Telescope](https://github.com/nvim-telescope/telescope.nvim)
- `oldfiles` in [fzf-lua](https://github.com/ibhagwan/fzf-lua)
- `recent` in [Snacks.picker](https://github.com/folke/snacks.nvim)

Since `oldfiles` tracks all the opened files, it may contain a lot of junks such as deleted files.

However, `oldfiles` is not easily modifiable because it is read from the ShaDa file when NeoVim starts, and removing from the `oldfiles` does not affect ShaDa file.

This script modifies the ShaDa file, which is in MessagePack format, and removes the marks, jumps, and change history from it so that those are not included in `oldfiles`.

# Features

- Remove from `oldfiles` that files do not exist in filesystem.
- Remove from `oldfiles` using regular expressions.
- Remove from `oldfiles` by selecting from the `fzf` command.

# TIPS

If you just want to ignore `/tmp/` file, you don't need this script. Add following to `shada` option.

```lua
vim.opt.shada:append({ "r/tmp/" })
```

Read `:help shada-r` for more detail.


# Requirements

- Neovim
- Python >= 3.9
- [msgpack](https://pypi.org/project/msgpack/) library >= 1.1.0
- fzf (Optional)

# Install

This is a small Python script that only uses only `msgpack` library, so just download [nvim-oldfiles-cleaner.py](./nvim-oldfiles-cleaner.py) and run it.

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
$ ./nvim-oldfiles-cleaner.py --fzf
```

When you provide items from `stdin`, those are also deleted. Therefore, the above is mostly equivalent to:

```bash
$ ./nvim-oldfiles-cleaner.py -l | fzf -m | ./nvim-oldfiles-cleaner.py
```

# Caveats

- The original Shada file is backed up to `~/.local/state/nvim/shada/main.shada.old` before writing it. If something goes wrong, restore it from this location.
- This script is only tested on Linux and macOS, so I don't know whether it works in Windows or not.

# Open Problems

- Can we write this script as pure Neovim plugin?
