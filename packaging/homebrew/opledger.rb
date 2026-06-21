# Homebrew formula for OPLedger.
#
# This file is the canonical source; publish it by copying to the tap repo
# `opieeipo/homebrew-opledger` (path: Formula/opledger.rb). Users then run:
#
#     brew tap opieeipo/opledger
#     brew install opledger
#     brew install --cask google-chrome   # required
#     opledger
#
# After tagging a release, update `version` and recompute `sha256` against the
# GitHub source tarball (see packaging/README.md).
class Opledger < Formula
  desc "Self-hosted, private bookkeeping: QFX in, Schedule C out"
  homepage "https://github.com/opieeipo/OPLedger"
  url "https://github.com/opieeipo/OPLedger/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SOURCE_TARBALL_SHA256"
  license :cant_represent # Apache-2.0 with the Commons Clause condition (see LICENSE)
  version "0.1.0"

  depends_on "podman"

  def install
    bin.install "packaging/launcher/opledger" => "opledger"
  end

  def caveats
    <<~EOS
      OPLedger runs as a Podman container and opens in Google Chrome.

        1. Install Chrome (required):  brew install --cask google-chrome
        2. Start Podman's VM once:      podman machine init && podman machine start
        3. Launch:                      opledger

      First launch pulls the container image and may take a minute. Closing the
      window stops the container. Your data stays in the local `opledger-data`
      Podman volume.
    EOS
  end

  test do
    assert_match "OPLedger", shell_output("#{bin}/opledger --help")
  end
end
