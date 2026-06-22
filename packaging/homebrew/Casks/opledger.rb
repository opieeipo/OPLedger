# Homebrew cask for the OPLedger native desktop app.
#
# Publish by copying to the tap repo `opieeipo/homebrew-opledger` at
# `Casks/opledger.rb`. Install:
#
#     brew install --cask opieeipo/opledger/opledger
#
# After a release tag builds the macOS asset, set `version` and `sha256`
# (see packaging/README.md).
cask "opledger" do
  version "0.2.1"
  sha256 "520399dd76ca1a5f55fbc25af0cd373aa440b245c2252d717d2930a4bf914d19"

  url "https://github.com/opieeipo/OPLedger/releases/download/v#{version}/OPLedger-v#{version}-macOS-arm64.zip"
  name "OPLedger"
  desc "Self-hosted, private bookkeeping: QFX in, Schedule C out"
  homepage "https://github.com/opieeipo/OPLedger"

  depends_on arch: :arm64
  depends_on macos: :big_sur

  app "OPLedger.app"

  zap trash: [
    "~/Library/Application Support/OPLedger",
  ]

  caveats <<~EOS
    Your encrypted ledger lives at ~/Library/Application Support/OPLedger.
    `brew uninstall` keeps it; only `--zap` removes it. Back up your passphrase —
    without it the data cannot be decrypted.
  EOS
end
