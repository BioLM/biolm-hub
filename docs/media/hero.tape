# hero.tape — "zero to serving" terminal cast for biolm-hub
# ---------------------------------------------------------------------------
# Records the real README quickstart: clone -> install -> setup -> deploy ->
# serve -> curl an embedding back. Renders to docs/media/hero.gif.
#
# PREREQUISITES
#   brew install vhs                 # https://github.com/charmbracelet/vhs
#   A Modal account + `modal token new`   (bh deploy ships to YOUR workspace)
#
#   VHS runs these commands for real, so a cold run is slow: `make install`
#   and the first `bh deploy esm2` each take minutes. For a tight ~20-30s hero
#   gif, record against a PRE-WARMED checkout — run `make install` once and
#   `bh deploy esm2` once beforehand so every step below returns in seconds.
#   The commands are the real quickstart, unchanged; only the environment is
#   primed. (Alternatively, record cold and speed up the long spans in post.)
#
# GENERATE
#   vhs docs/media/hero.tape         # writes docs/media/hero.gif
# ---------------------------------------------------------------------------

Output docs/media/hero.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 720
Set Theme "Catppuccin Mocha"
Set TypingSpeed 55ms
Set Padding 24

# 1 - Clone and enter the repo
Type "git clone https://github.com/BioLM/biolm-hub && cd biolm-hub"
Enter
Sleep 3s

# 2 - Install: venv + all deps + the `bh` CLI, then activate it
Type "make install"
Enter
Sleep 4s
Type "source .venv/bin/activate"
Enter
Sleep 1s

# 3 - Check Modal auth (the only account you need)
Type "bh setup"
Enter
Sleep 3s

# 4 - Deploy ESM-2's default variant (esm2-8m, CPU-only) to your Modal
Type "bh deploy esm2"
Enter
Sleep 5s

# 5 - Serve the gateway: HTTP API + browser catalog UI on :8000
Type "bh serve &"
Enter
Sleep 3s

# 6 - Call it. Same 6 verbs across all 37 models -> embeddings come back.
Type `curl -s http://127.0.0.1:8000/api/v1/esm2-8m/encode \`
Enter
Type `  -H "Content-Type: application/json" \`
Enter
Type `  -d '{"items": [{"sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"}]}'`
Enter
Sleep 7s
