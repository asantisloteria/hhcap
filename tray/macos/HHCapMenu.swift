// Indicador de barra de menú para hhcap. Compilar: swiftc -O HHCapMenu.swift -o hhcap-menu
import AppKit

func hhcapPath() -> String {
    let env = ProcessInfo.processInfo.environment
    if let p = env["HHCAP_BIN"], FileManager.default.isExecutableFile(atPath: p) { return p }
    let exeDir = (CommandLine.arguments[0] as NSString).resolvingSymlinksInPath
    var candidates = [((exeDir as NSString).deletingLastPathComponent as NSString).appendingPathComponent("hhcap")]
    candidates += ["/opt/homebrew/bin/hhcap", "/usr/local/bin/hhcap", NSHomeDirectory() + "/.local/bin/hhcap"]
    return candidates.first { FileManager.default.isExecutableFile(atPath: $0) } ?? "hhcap"
}

@discardableResult
func run(_ args: [String]) -> (Int32, String) {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    p.arguments = [hhcapPath()] + args
    let pipe = Pipe()
    p.standardOutput = pipe
    p.standardError = pipe
    do { try p.run() } catch { return (127, "\(error)") }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    return (p.terminationStatus, String(data: data, encoding: .utf8) ?? "")
}

final class App: NSObject, NSApplicationDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let info = NSMenuItem(title: "…", action: nil, keyEquivalent: "")
    let ultimo = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    var timer: Timer?

    func applicationDidFinishLaunching(_ n: Notification) {
        let m = NSMenu()
        m.addItem(info)
        m.addItem(ultimo)
        ultimo.isHidden = true
        m.addItem(.separator())
        m.addItem(withTitle: "Ya marqué entrada", action: #selector(entrada), keyEquivalent: "e").target = self
        m.addItem(withTitle: "Ya marqué salida", action: #selector(salida), keyEquivalent: "s").target = self
        m.addItem(withTitle: "Ver semana", action: #selector(semana), keyEquivalent: "r").target = self
        m.addItem(.separator())
        m.addItem(withTitle: "Salir", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        item.menu = m
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func refresh() {
        let (rc, out) = run(["status", "--json"])
        guard rc == 0, let d = out.data(using: .utf8),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let estado = j["estado"] as? String else {
            item.button?.title = "⚪️"
            info.title = "hhcap no responde"
            return
        }
        let mins = j["minutos"] as? Int ?? 0
        let tipo = j["tipo"] as? String ?? ""
        let reloj = String(format: "%d:%02d", mins / 60, mins % 60)
        switch estado {
        case "en_horario":
            item.button?.title = "🟢"
            let jor = j["jornada"] as? [String] ?? []
            info.title = jor.count == 2 ? "En horario (\(jor[0])–\(jor[1]))" : "En horario"
        case "extra_abierta":
            item.button?.title = "🟡 \(reloj)"
            info.title = "Hora extra \(tipo) abierta: \(reloj)"
        case "extra_por_cerrar":
            item.button?.title = "🟠 \(reloj)"
            info.title = "Inactivo: marca salida en GeoVictoria"
        default:
            item.button?.title = "🔴"
            info.title = "Fuera de horario (\(tipo)) sin marca"
        }
        if let aviso = j["aviso"] as? String { info.toolTip = aviso; item.button?.title += "⚠︎" }
    }

    func mostrar(_ msg: String) {
        ultimo.title = msg.trimmingCharacters(in: .whitespacesAndNewlines)
        ultimo.isHidden = ultimo.title.isEmpty
        refresh()
    }

    @objc func entrada() { mostrar(run(["marque-entrada"]).1) }
    @objc func salida() { mostrar(run(["marque-salida"]).1) }

    @objc func semana() {
        let out = run(["reporte", "--semana"]).1
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("hhcap-semana.txt")
        try? out.write(to: url, atomically: true, encoding: .utf8)
        NSWorkspace.shared.open(url)
    }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
