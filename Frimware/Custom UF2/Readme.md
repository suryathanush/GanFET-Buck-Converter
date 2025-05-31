## Custom UF2 Setup for Raspi Pico
To make a custom UF2, install the software tool picotool. The setup process will vary depending on your computer, and what’s outlined below is based on a macOs installation. I used previously-installed package manager Homebrew to add picotool to my computer by following these instructions, which worked flawlessly.

Set up your dev board exactly as you would like it to be duplicated, including any libraries and/or additional files. Restart your RP2040 in BOOTSEL mode; for the Pico, hold down its button while plugging it in. Enter the following on your command line:

```console
picotool save --all full_duplicated_board.uf2
```

This will save your board as a UF2 file in your home directory as “full_duplicated_board.uf2.” This can then be copied onto a new device plugged into your computer. Copy, paste, and wait for the process to complete. Your new board will have all the software properties of the original.