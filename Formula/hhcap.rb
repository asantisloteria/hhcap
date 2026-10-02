# El mismo repo sirve de tap:  brew tap asantisloteria/hhcap https://github.com/asantisloteria/hhcap.git
# scripts/release.sh actualiza el tag de abajo en cada versión.
class Hhcap < Formula
  desc "Captador de horas extras: gate de Claude Code fuera de horario"
  homepage "https://github.com/asantisloteria/hhcap"
  url "https://github.com/asantisloteria/hhcap.git", tag: "v0.1.0"
  head "https://github.com/asantisloteria/hhcap.git", branch: "main"

  depends_on :macos

  def install
    libexec.install "hhcap"
    (bin/"hhcap").write <<~SH
      #!/bin/bash
      PYTHONPATH="#{libexec}" exec /usr/bin/python3 -m hhcap "$@"
    SH
    system "swiftc", "-O", "tray/macos/HHCapMenu.swift", "-o", bin/"hhcap-menu"
  end

  service do
    run opt_bin/"hhcap-menu"
    keep_alive false
    run_at_load true
  end

  def caveats
    <<~EOS
      1. Configura tu jornada:   hhcap config --jornada lun=08:15-17:45 ... --jornada vie=08:15-13:35
      2. Activa el bloqueo:      hhcap hook install
      3. Indicador al iniciar:   brew services start hhcap
      Actualizar:                hhcap update
    EOS
  end

  test do
    assert_match "hhcap", shell_output("#{bin}/hhcap --version")
    ENV["HHCAP_HOME"] = testpath
    ENV["HHCAP_NOW"] = "2026-10-03T10:00"
    assert_match "\"continue\": false", pipe_output("#{bin}/hhcap hook prompt", '{"prompt":"x"}')
  end
end
