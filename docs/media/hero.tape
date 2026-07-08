# hero.tape — biolm-hub "few steps to a serving model"
# ---------------------------------------------------------------------------
# Renders to docs/media/hero.{gif,mp4}. The `curl` runs for real against a
# Modal-backed gateway (env: biolm-hub-dev), so the embeddings shown are
# genuine. The one-time setup (clone/install/deploy) and `bh serve` are
# narrated — a live Modal build / gateway boot doesn't record cleanly inside
# VHS's pseudo-terminal, so the gateway is started out-of-frame beforehand and
# this tape shows the payoff: calling a served model over the uniform API.
#
# PREREQUISITES (done out-of-frame before rendering)
#   brew install vhs ; bh deploy esm2 ; bh serve --port 8000   (gateway live)
# GENERATE
#   vhs docs/media/hero.tape         # writes docs/media/hero.gif + hero.mp4
# ---------------------------------------------------------------------------

Output docs/media/hero.gif
Output docs/media/hero.mp4

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set TypingSpeed 42ms
Set Padding 24

# --- off-camera: real checkout, activated venv ---
Hide
Type "cd /Users/qamar/dev/biolm-hub && source .venv/bin/activate && clear"
Enter
Sleep 2s
Show

Type "# biolm-hub — one uniform HTTP API over 37 open biological ML models."
Enter
Type "# 1. git clone .../biolm-hub && cd biolm-hub && make install"
Enter
Type "# 2. bh deploy esm2      # ship ESM-2 (8M, CPU) to YOUR Modal account"
Enter
Type "# 3. bh serve            # HTTP API + browser catalog, now live on :8000"
Enter
Sleep 2s
Enter

Type "# Call any model — the same 6 verbs everywhere. Real embeddings come back:"
Enter
Type `curl -s http://127.0.0.1:8000/api/v1/esm2-8m/encode \`
Enter
Type `  -H "Content-Type: application/json" \`
Enter
Type `  -d '{"items":[{"sequence":"MKTVRQERLKSIVRILERSKEPVSGAQLAEEL"}]}' | head -c 200`
Enter
Wait+Screen@60s /embeddings/
Sleep 4s
