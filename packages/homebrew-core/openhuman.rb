class Openhuman < Formula
  desc "AI-powered personal assistant for communities"
  homepage "https://eversilver.local/eversilver"
  url "https://github.com/eversilver/eversilver/archive/refs/tags/v0.52.27.tar.gz"
  sha256 "e85c95db1865f325f55b6b886c1ff0296e40d5405a9e5aa03f27310d43993a52"
  license "GPL-3.0-only"
  head "https://github.com/eversilver/eversilver.git", branch: "main"

  depends_on "cmake" => :build
  depends_on "pkgconf" => :build
  depends_on "rust" => :build

  on_linux do
    depends_on "openssl@3"
  end

  def install
    ENV["OPENSSL_NO_VENDOR"] = "1" if OS.linux?

    system "cargo", "install", "--bin", "eversilver-core", *std_cargo_args
    bin.install_symlink bin/"eversilver-core" => "eversilver"
  end

  test do
    assert_match "Eversilver core CLI", shell_output("#{bin}/eversilver --help")
    assert_match "Eversilver core CLI", shell_output("#{bin}/eversilver-core --help")
  end
end
