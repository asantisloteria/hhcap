// Indicador de barra de menú para hhcap. Se empaqueta como HHCap.app (ver Makefile) para que las
// notificaciones salgan con su ícono.
import AppKit
import UniformTypeIdentifiers
import UserNotifications

func hhcapPath() -> String {
    let env = ProcessInfo.processInfo.environment
    if let p = env["HHCAP_BIN"], FileManager.default.isExecutableFile(atPath: p) { return p }
    let candidatos = ["/opt/homebrew/bin/hhcap", "/usr/local/bin/hhcap", NSHomeDirectory() + "/.local/bin/hhcap"]
    return candidatos.first { FileManager.default.isExecutableFile(atPath: $0) } ?? "hhcap"
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

/// Pide un texto con un diálogo. nil si se cancela.
func pedirTexto(titulo: String, mensaje: String, valor: String, boton: String) -> String? {
    NSApp.activate(ignoringOtherApps: true)
    let a = NSAlert()
    a.messageText = titulo
    a.informativeText = mensaje
    a.addButton(withTitle: boton)
    a.addButton(withTitle: "Cancelar")
    let campo = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
    campo.stringValue = valor
    campo.placeholderString = "Ej: deploy de producción, incidente en pagos…"
    a.accessoryView = campo
    a.window.initialFirstResponder = campo
    return a.runModal() == .alertFirstButtonReturn ? campo.stringValue.trimmingCharacters(in: .whitespaces) : nil
}

// MARK: - Estilo

struct Estilo {
    let titulo: String, simbolo: String, fondo: NSColor, tinta: NSColor

    static func de(_ estado: String) -> Estilo {
        switch estado {
        case "en_horario":
            return Estilo(titulo: "En horario", simbolo: "checkmark",
                          fondo: NSColor(srgbRed: 0.13, green: 0.62, blue: 0.36, alpha: 1), tinta: .white)
        case "extra_abierta":
            return Estilo(titulo: "Hora extra", simbolo: "timer",
                          fondo: NSColor(srgbRed: 0.98, green: 0.73, blue: 0.13, alpha: 1), tinta: .black)
        case "extra_por_cerrar":
            return Estilo(titulo: "Cierra tu extra", simbolo: "hourglass",
                          fondo: NSColor(srgbRed: 0.96, green: 0.45, blue: 0.10, alpha: 1), tinta: .white)
        case "fuera_sin_marca":
            return Estilo(titulo: "Fuera de horario", simbolo: "moon.fill",
                          fondo: NSColor(srgbRed: 0.90, green: 0.24, blue: 0.27, alpha: 1), tinta: .white)
        default:
            return Estilo(titulo: "hhcap", simbolo: "questionmark", fondo: .systemGray, tinta: .white)
        }
    }

    func icono(_ puntos: CGFloat, color: NSColor? = nil) -> NSImage? {
        NSImage(systemSymbolName: simbolo, accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: puntos, weight: .bold).applying(.init(paletteColors: [color ?? tinta])))
    }
}

/// Pastilla estilo Uber para la barra de menú: cápsula negra, texto blanco en negrita y el color
/// del semáforo solo como acento en el ícono (que late con `alfa`).
func pastilla(_ texto: String, _ e: Estilo, alfa: CGFloat = 1) -> NSImage {
    let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.monospacedDigitSystemFont(ofSize: 12, weight: .bold),
                                                .foregroundColor: NSColor.white]
    let t = texto as NSString
    let tam = t.size(withAttributes: attrs)
    let simbolo = e.icono(10, color: e.fondo.withAlphaComponent(alfa))
    let alto: CGFloat = 19, pad: CGFloat = 8, gap: CGFloat = 5
    let ancho = ceil(pad + (simbolo?.size.width ?? 0) + gap + tam.width + pad)
    return NSImage(size: NSSize(width: ancho, height: alto), flipped: false) { r in
        NSColor.black.setFill()
        NSBezierPath(roundedRect: r, xRadius: alto / 2, yRadius: alto / 2).fill()
        if let s = simbolo { s.draw(in: NSRect(x: pad, y: (alto - s.size.height) / 2, width: s.size.width, height: s.size.height)) }
        t.draw(at: NSPoint(x: pad + (simbolo?.size.width ?? 0) + gap, y: (alto - tam.height) / 2), withAttributes: attrs)
        return true
    }
}

/// Tarjeta de estado al tope del menú: ícono en círculo de acento, título y detalle, y a la derecha
/// un número grande con su leyenda (tiempo de extra, o lo que falta para terminar la jornada).
final class Tarjeta: NSView {
    let circulo = NSView(), icono = NSImageView()
    let titulo = etiqueta("", tam: 14, peso: .semibold, color: .labelColor)
    let detalle = etiqueta("", tam: 12, peso: .regular, color: .secondaryLabelColor)
    let numero = etiqueta("", tam: 20, peso: .bold, color: .labelColor)
    let leyenda = etiqueta("", tam: 10, peso: .medium, color: .secondaryLabelColor)

    init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 300, height: 66))
        circulo.wantsLayer = true
        circulo.layer?.cornerRadius = 18
        circulo.frame = NSRect(x: 16, y: 15, width: 36, height: 36)
        icono.frame = NSRect(x: 9, y: 9, width: 18, height: 18)
        icono.imageScaling = .scaleProportionallyUpOrDown
        circulo.addSubview(icono)
        titulo.frame = NSRect(x: 64, y: 34, width: 150, height: 18)
        detalle.frame = NSRect(x: 64, y: 15, width: 160, height: 16)
        numero.font = .monospacedDigitSystemFont(ofSize: 20, weight: .bold)
        numero.alignment = .right
        numero.frame = NSRect(x: 200, y: 30, width: 86, height: 24)
        leyenda.alignment = .right
        leyenda.frame = NSRect(x: 180, y: 15, width: 106, height: 14)
        [circulo, titulo, detalle, numero, leyenda].forEach(addSubview)
    }
    required init?(coder: NSCoder) { fatalError() }

    func poner(_ e: Estilo, titulo t: String, detalle d: String, numero n: String = "", leyenda l: String = "") {
        circulo.layer?.backgroundColor = e.fondo.withAlphaComponent(0.2).cgColor
        icono.image = e.icono(14, color: e.fondo)
        titulo.stringValue = t
        detalle.stringValue = d
        numero.stringValue = n
        leyenda.stringValue = l
    }
}

/// 145 -> "2h 25m"; 25 -> "25m".
func horasMinutos(_ m: Int) -> String { m >= 60 ? "\(m / 60)h \(m % 60)m" : "\(m)m" }

func etiqueta(_ t: String, tam: CGFloat, peso: NSFont.Weight, color: NSColor, mono: Bool = false) -> NSTextField {
    let l = NSTextField(labelWithString: t)
    l.font = mono ? .monospacedSystemFont(ofSize: tam, weight: peso) : .systemFont(ofSize: tam, weight: peso)
    l.textColor = color
    return l
}

/// Botón plano estilo Uber: primario blanco con texto negro; secundario solo texto.
final class BotonUber: NSButton {
    convenience init(titulo: String, primario: Bool, target: AnyObject?, action: Selector) {
        self.init(frame: .zero)
        self.target = target
        self.action = action
        isBordered = false
        wantsLayer = true
        layer?.cornerRadius = 10
        layer?.backgroundColor = primario ? NSColor.white.cgColor : NSColor.clear.cgColor
        attributedTitle = NSAttributedString(string: titulo, attributes: [
            .font: NSFont.systemFont(ofSize: primario ? 14 : 13, weight: primario ? .bold : .medium),
            .foregroundColor: primario ? NSColor.black : NSColor(white: 0.65, alpha: 1)])
        if primario { keyEquivalent = "\r" }
    }
}

// MARK: - App

final class App: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let tarjeta = Tarjeta()
    let ultimo = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    let popover = NSPopover()
    var estado = "", texto = "hhcap", aviso: String?, motivoActual = ""
    var ticks = 0
    var ultimoBloqueo: Date?
    let bloqueoURL = URL(fileURLWithPath: NSHomeDirectory() + "/.hhcap/bloqueo.json")
    var ventana: VentanaHoras?
    var itemEntrada: NSMenuItem?, itemSalida: NSMenuItem?

    func applicationDidFinishLaunching(_ n: Notification) {
        let m = NSMenu()
        let cab = NSMenuItem()
        cab.view = tarjeta
        m.addItem(cab)
        m.addItem(ultimo)
        ultimo.isHidden = true
        m.addItem(.separator())
        itemEntrada = agregar(m, "Ya marqué entrada", "arrow.right.circle", #selector(entrada), "e")
        itemSalida = agregar(m, "Ya marqué salida", "arrow.left.circle", #selector(salida), "s")
        agregar(m, "Justificación…", "text.bubble", #selector(motivo), "j")
        m.addItem(.separator())
        agregar(m, "Ver mis horas extras", "tablecells", #selector(verHoras), "r")
        m.addItem(.separator())
        agregar(m, "Salir", "power", #selector(NSApplication.terminate(_:)), "q", objetivo: nil)
        item.menu = m
        popover.behavior = .transient

        if Bundle.main.bundleIdentifier != nil {
            let centro = UNUserNotificationCenter.current()
            centro.delegate = self
            centro.requestAuthorization(options: [.alert, .sound]) { _, _ in }
        }
        ultimoBloqueo = fechaBloqueo()
        refresh()
        // Un tick por segundo: latido en rojo y aviso de bloqueo; estado completo cada 30 s.
        Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
        if CommandLine.arguments.contains("--horas") { verHoras() }
        if CommandLine.arguments.contains("--demo-menu") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in self?.item.button?.performClick(nil) }
        }
    }

    @discardableResult
    func agregar(_ m: NSMenu, _ t: String, _ simbolo: String, _ accion: Selector, _ tecla: String, objetivo: AnyObject? = nil) -> NSMenuItem {
        let i = m.addItem(withTitle: t, action: accion, keyEquivalent: tecla)
        i.target = objetivo ?? self
        if accion == #selector(NSApplication.terminate(_:)) { i.target = NSApp }
        i.image = NSImage(systemSymbolName: simbolo, accessibilityDescription: nil)
        return i
    }

    func tick() {
        ticks += 1
        if ticks % 30 == 0 { refresh() }
        if let f = fechaBloqueo(), f != ultimoBloqueo {
            ultimoBloqueo = f
            refresh()
            avisarBloqueo()
        }
        pintar()
    }

    func pintar() {
        let alfa: CGFloat = estado == "fuera_sin_marca" && ticks % 2 == 1 ? 0.25 : 1
        item.button?.title = ""
        item.button?.image = pastilla(texto + (aviso != nil ? "  ⚠︎" : ""), Estilo.de(estado), alfa: alfa)
        item.button?.toolTip = aviso
    }

    func fechaBloqueo() -> Date? {
        (try? FileManager.default.attributesOfItem(atPath: bloqueoURL.path))?[.modificationDate] as? Date
    }

    // MARK: Aviso de bloqueo (globo + notificación)

    func avisarBloqueo() {
        mostrarGlobo()
        guard Bundle.main.bundleIdentifier != nil else { return }
        let c = UNMutableNotificationContent()
        c.title = "Fuera de horario"
        c.body = "Marca entrada en GeoVictoria y confirma con «Ya marqué entrada»."
        c.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: "bloqueo", content: c, trigger: nil))
    }

    func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification,
                                withCompletionHandler h: @escaping (UNNotificationPresentationOptions) -> Void) {
        h([.banner, .sound])
    }

    func mostrarGlobo() {
        guard let boton = item.button else { return }
        let e = Estilo.de("fuera_sin_marca")
        let W: CGFloat = 320, pad: CGFloat = 20
        let vista = NSView(frame: NSRect(x: 0, y: 0, width: W, height: 252))
        vista.wantsLayer = true
        vista.layer?.backgroundColor = NSColor(white: 0.06, alpha: 1).cgColor

        // Ícono en círculo de acento.
        let circulo = NSView(frame: NSRect(x: pad, y: 192, width: 40, height: 40))
        circulo.wantsLayer = true
        circulo.layer?.cornerRadius = 20
        circulo.layer?.backgroundColor = e.fondo.withAlphaComponent(0.18).cgColor
        let ic = NSImageView(frame: NSRect(x: 10, y: 10, width: 20, height: 20))
        ic.image = e.icono(15, color: e.fondo)
        circulo.addSubview(ic)

        let tt = etiqueta("Fuera de horario", tam: 20, peso: .bold, color: .white)
        tt.frame = NSRect(x: pad + 52, y: 207, width: W - pad * 2 - 52, height: 26)
        let sub = etiqueta("Claude Code está en pausa", tam: 12, peso: .medium, color: NSColor(white: 0.6, alpha: 1))
        sub.frame = NSRect(x: pad + 52, y: 190, width: W - pad * 2 - 52, height: 16)

        let cuerpo = NSTextField(wrappingLabelWithString: "Marca tu entrada en GeoVictoria y confírmala aquí o en Claude Code con:")
        cuerpo.font = .systemFont(ofSize: 13)
        cuerpo.textColor = NSColor(white: 0.82, alpha: 1)
        cuerpo.frame = NSRect(x: pad, y: 138, width: W - pad * 2, height: 36)

        // Comando en un recuadro.
        let chip = NSView(frame: NSRect(x: pad, y: 100, width: W - pad * 2, height: 30))
        chip.wantsLayer = true
        chip.layer?.cornerRadius = 8
        chip.layer?.backgroundColor = NSColor(white: 0.16, alpha: 1).cgColor
        let cmd = etiqueta("! hhcap marque-entrada", tam: 12, peso: .medium, color: .white, mono: true)
        cmd.frame = NSRect(x: 12, y: 7, width: W - pad * 2 - 24, height: 16)
        chip.addSubview(cmd)

        let si = BotonUber(titulo: "Ya marqué entrada", primario: true, target: self, action: #selector(entradaDesdeGlobo))
        si.frame = NSRect(x: pad, y: 46, width: W - pad * 2, height: 40)
        let no = BotonUber(titulo: "Ahora no", primario: false, target: popover, action: #selector(NSPopover.performClose(_:)))
        no.frame = NSRect(x: pad, y: 10, width: W - pad * 2, height: 30)

        [circulo, tt, sub, cuerpo, chip, si, no].forEach(vista.addSubview)
        let vc = NSViewController()
        vc.view = vista
        vc.preferredContentSize = vista.frame.size
        popover.appearance = NSAppearance(named: .darkAqua)
        popover.contentViewController = vc
        popover.contentSize = vista.frame.size
        popover.show(relativeTo: boton.bounds, of: boton, preferredEdge: .minY)
        DispatchQueue.main.asyncAfter(deadline: .now() + 15) { [weak self] in self?.popover.performClose(nil) }
    }

    @objc func entradaDesdeGlobo() {
        popover.performClose(nil)
        entrada()
    }

    // MARK: Estado

    func refresh() {
        let (rc, out) = run(["status", "--json"])
        guard rc == 0, let d = out.data(using: .utf8),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let e = j["estado"] as? String else {
            estado = ""; texto = "hhcap ?"; aviso = nil
            tarjeta.poner(Estilo.de(""), titulo: "hhcap no responde", detalle: "Revisa la instalación")
            pintar()
            return
        }
        estado = e
        let mins = j["minutos"] as? Int ?? 0
        let tipo = j["tipo"] as? String ?? ""
        let r = String(format: "%d:%02d", mins / 60, mins % 60)
        let extra = j["extra"] as? [String: Any]
        let desde = (extra?["inicio"] as? String).map { String($0.dropFirst(11).prefix(5)) } ?? ""
        motivoActual = extra?["motivo"] as? String ?? ""
        let st = Estilo.de(e)
        switch e {
        case "en_horario":
            texto = "En horario"
            let jor = j["jornada"] as? [String] ?? []
            var falta = ""
            if jor.count == 2, let ahora = j["ahora"] as? String {
                let hm = { (x: Substring) -> Int in Int(x.prefix(2))! * 60 + Int(x.dropFirst(3).prefix(2))! }
                let m = max(0, hm(Substring(jor[1])) - hm(ahora.dropFirst(11)))
                falta = horasMinutos(m)
            }
            tarjeta.poner(st, titulo: "En horario", detalle: jor.count == 2 ? "Jornada \(jor[0])–\(jor[1])" : "",
                          numero: falta, leyenda: falta.isEmpty ? "" : "para salir")
        case "extra_abierta":
            texto = "Extra \(tipo) · \(r)"
            tarjeta.poner(st, titulo: "Hora extra \(tipo)", detalle: "Desde las \(desde)", numero: horasMinutos(mins), leyenda: "acumulado")
        case "extra_por_cerrar":
            texto = "Cierra tu extra · \(r)"
            tarjeta.poner(st, titulo: "¿Terminaste?", detalle: "Marca salida en GeoVictoria", numero: horasMinutos(mins), leyenda: "acumulado")
        default:
            texto = "Fuera de horario"
            tarjeta.poner(st, titulo: "Fuera de horario", detalle: "Marca entrada para usar Claude", numero: tipo, leyenda: "si trabajas")
        }
        aviso = j["aviso"] as? String
        // Solo la acción que corresponde al estado. En horario no se marca nada, salvo cerrar una extra olvidada.
        let hayExtra = extra != nil
        itemEntrada?.isHidden = e != "fuera_sin_marca"
        itemSalida?.isHidden = !hayExtra
        pintar()
    }

    func mostrar(_ msg: String) {
        ultimo.title = msg.trimmingCharacters(in: .whitespacesAndNewlines)
        ultimo.isHidden = ultimo.title.isEmpty
        refresh()
        ventana?.cargar()
    }

    @objc func entrada() { mostrar(run(["marque-entrada"]).1) }

    @objc func salida() {
        guard let m = pedirTexto(titulo: "Marcar salida",
                                 mensaje: "¿En qué trabajaste? Queda como justificación para el Comentario de SAP.",
                                 valor: motivoActual, boton: "Marcar salida") else { return }
        mostrar(run(m.isEmpty ? ["marque-salida"] : ["marque-salida", "--motivo", m]).1)
    }

    @objc func motivo() {
        let abierta = estado == "extra_abierta" || estado == "extra_por_cerrar"
        guard let m = pedirTexto(titulo: "Justificación",
                                 mensaje: abierta ? "Para la hora extra en curso." : "Para tu último bloque de horas extras.",
                                 valor: abierta ? motivoActual : "", boton: "Guardar"), !m.isEmpty else { return }
        mostrar(run(["motivo", m]).1)
    }

    @objc func verHoras() {
        if ventana == nil { ventana = VentanaHoras() }
        ventana?.mostrar()
    }
}

/// Tarjeta de resumen: etiqueta pequeña y número grande.
final class TarjetaNumero: NSView {
    let valor = NSTextField(labelWithString: "0:00")
    init(titulo: String, acento: NSColor) {
        super.init(frame: .zero)
        wantsLayer = true
        layer?.cornerRadius = 12
        layer?.backgroundColor = NSColor(white: 0.1, alpha: 1).cgColor
        let t = etiqueta(titulo, tam: 11, peso: .semibold, color: NSColor(white: 0.5, alpha: 1))
        valor.font = .monospacedDigitSystemFont(ofSize: 28, weight: .bold)
        valor.textColor = acento
        let pila = NSStackView(views: [t, valor])
        pila.orientation = .vertical
        pila.alignment = .leading
        pila.spacing = 2
        pila.translatesAutoresizingMaskIntoConstraints = false
        addSubview(pila)
        NSLayoutConstraint.activate([
            pila.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16),
            pila.centerYAnchor.constraint(equalTo: centerYAnchor),
            heightAnchor.constraint(equalToConstant: 78),
        ])
    }
    required init?(coder: NSCoder) { fatalError() }
}

// MARK: - Ventana "Ver mis horas extras"

struct Fila { let dia, fecha, desde, hasta, duracion, tipo, motivo, inicio: String; let vacia: Bool }

final class VentanaHoras: NSObject, NSTableViewDataSource, NSTableViewDelegate, NSWindowDelegate {
    let ventana: NSWindow
    let tabla = NSTableView()
    let titulo = NSTextField(labelWithString: "")
    var filas: [Fila] = []
    var dia = Date()
    let iso: DateFormatter = { let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX"); return f }()
    let largo: DateFormatter = { let f = DateFormatter(); f.dateFormat = "d MMM"; f.locale = Locale(identifier: "es_CL"); return f }()
    let corto: DateFormatter = { let f = DateFormatter(); f.dateFormat = "dd/MM"; return f }()
    let nombreDia: DateFormatter = { let f = DateFormatter(); f.dateFormat = "EEEE"; f.locale = Locale(identifier: "es_CL"); return f }()
    let columnas: [(String, String, CGFloat)] = [("dia", "Día", 86), ("fecha", "Fecha", 50), ("desde", "Desde", 52),
        ("hasta", "Hasta", 52), ("duracion", "Duración", 70), ("tipo", "Tipo", 46), ("motivo", "Motivo", 260)]

    let tarjetaTotal = TarjetaNumero(titulo: "TOTAL", acento: .white)
    let tarjeta50 = TarjetaNumero(titulo: "AL 50%", acento: Estilo.de("extra_abierta").fondo)
    let tarjeta100 = TarjetaNumero(titulo: "AL 100%", acento: Estilo.de("fuera_sin_marca").fondo)

    override init() {
        ventana = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 560),
                           styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                           backing: .buffered, defer: false)
        super.init()
        ventana.title = "Mis horas extras"
        ventana.titleVisibility = .hidden
        ventana.titlebarAppearsTransparent = true
        ventana.appearance = NSAppearance(named: .darkAqua)
        ventana.backgroundColor = NSColor(white: 0.06, alpha: 1)
        ventana.isReleasedWhenClosed = false
        ventana.minSize = NSSize(width: 680, height: 420)
        ventana.delegate = self

        let encabezado = etiqueta("Mis horas extras", tam: 26, peso: .bold, color: .white)
        titulo.font = .systemFont(ofSize: 14, weight: .medium)
        titulo.textColor = NSColor(white: 0.6, alpha: 1)
        let textos = NSStackView(views: [encabezado, titulo])
        textos.orientation = .vertical
        textos.alignment = .leading
        textos.spacing = 2

        let atras = BotonUber(titulo: "‹", primario: false, target: self, action: #selector(anterior))
        let hoy = BotonUber(titulo: "Esta semana", primario: false, target: self, action: #selector(irHoy))
        let adelante = BotonUber(titulo: "›", primario: false, target: self, action: #selector(siguiente))
        for b in [atras, hoy, adelante] { b.layer?.backgroundColor = NSColor(white: 0.16, alpha: 1).cgColor }
        let bajar = BotonUber(titulo: "Descargar", primario: true, target: self, action: #selector(menuDescarga(_:)))
        bajar.keyEquivalent = ""
        NSLayoutConstraint.activate([
            atras.widthAnchor.constraint(equalToConstant: 34), adelante.widthAnchor.constraint(equalToConstant: 34),
            hoy.widthAnchor.constraint(equalToConstant: 104), bajar.widthAnchor.constraint(equalToConstant: 112),
        ] + [atras, hoy, adelante, bajar].map { $0.heightAnchor.constraint(equalToConstant: 32) })

        let espacio = NSView()
        espacio.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let cabecera = NSStackView(views: [textos, espacio, atras, hoy, adelante, bajar])
        cabecera.spacing = 8
        cabecera.alignment = .centerY

        let resumen = NSStackView(views: [tarjetaTotal, tarjeta50, tarjeta100])
        resumen.distribution = .fillEqually
        resumen.spacing = 12

        for (id, nombre, ancho) in columnas {
            let c = NSTableColumn(identifier: .init(id))
            c.title = nombre.uppercased()
            c.width = ancho
            c.headerCell.attributedStringValue = NSAttributedString(string: nombre.uppercased(), attributes: [
                .font: NSFont.systemFont(ofSize: 10, weight: .semibold), .foregroundColor: NSColor(white: 0.5, alpha: 1)])
            tabla.addTableColumn(c)
        }
        tabla.dataSource = self
        tabla.delegate = self
        tabla.backgroundColor = .clear
        tabla.rowHeight = 34
        tabla.intercellSpacing = NSSize(width: 8, height: 0)
        tabla.style = .plain
        tabla.gridStyleMask = .solidHorizontalGridLineMask
        tabla.gridColor = NSColor(white: 1, alpha: 0.06)
        tabla.selectionHighlightStyle = .none
        tabla.target = self
        tabla.doubleAction = #selector(editarMotivo)
        let scroll = NSScrollView()
        scroll.documentView = tabla
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.wantsLayer = true
        scroll.layer?.cornerRadius = 12
        scroll.layer?.backgroundColor = NSColor(white: 0.1, alpha: 1).cgColor

        let ayuda = etiqueta("Doble clic en una fila para escribir la justificación (va al Comentario de SAP).",
                             tam: 11, peso: .regular, color: NSColor(white: 0.45, alpha: 1))
        let firma = etiqueta("hhcap · by b1to", tam: 11, peso: .medium, color: NSColor(white: 0.35, alpha: 1))
        let espacio2 = NSView()
        espacio2.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let pie = NSStackView(views: [ayuda, espacio2, firma])

        let todo = NSStackView(views: [cabecera, resumen, scroll, pie])
        todo.orientation = .vertical
        todo.alignment = .leading
        todo.spacing = 16
        todo.edgeInsets = NSEdgeInsets(top: 40, left: 24, bottom: 18, right: 24)
        todo.translatesAutoresizingMaskIntoConstraints = false
        ventana.contentView = NSView()
        ventana.contentView!.addSubview(todo)
        NSLayoutConstraint.activate([
            todo.leadingAnchor.constraint(equalTo: ventana.contentView!.leadingAnchor),
            todo.trailingAnchor.constraint(equalTo: ventana.contentView!.trailingAnchor),
            todo.topAnchor.constraint(equalTo: ventana.contentView!.topAnchor),
            todo.bottomAnchor.constraint(equalTo: ventana.contentView!.bottomAnchor),
            cabecera.widthAnchor.constraint(equalTo: todo.widthAnchor, constant: -48),
            resumen.widthAnchor.constraint(equalTo: todo.widthAnchor, constant: -48),
            scroll.widthAnchor.constraint(equalTo: todo.widthAnchor, constant: -48),
            pie.widthAnchor.constraint(equalTo: todo.widthAnchor, constant: -48),
        ])
    }

    @objc func menuDescarga(_ b: NSButton) {
        let m = NSMenu()
        m.addItem(withTitle: "Semana (CSV para Excel)", action: #selector(bajarSemana), keyEquivalent: "").target = self
        m.addItem(withTitle: "Mes (CSV para Excel)", action: #selector(bajarMes), keyEquivalent: "").target = self
        m.popUp(positioning: nil, at: NSPoint(x: 0, y: b.bounds.height + 4), in: b)
    }

    func mostrar() {
        cargar()
        ventana.center()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        ventana.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ n: Notification) { NSApp.setActivationPolicy(.accessory) }

    func cargar() {
        let (rc, out) = run(["reporte", "--json", "--fecha", iso.string(from: dia)])
        guard rc == 0, let d = out.data(using: .utf8),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let dias = j["dias"] as? [String], let fs = j["filas"] as? [[String: Any]],
              let tot = j["totales"] as? [String: Int] else {
            titulo.stringValue = "No pude leer el reporte"
            return
        }
        let f = { (m: Int) in String(format: "%d:%02d", m / 60, m % 60) }
        filas = []
        for ds in dias {
            let fecha = iso.date(from: ds)!
            let delDia = fs.filter { $0["fecha"] as? String == ds }
            let nombre = nombreDia.string(from: fecha).capitalized
            if delDia.isEmpty {
                filas.append(Fila(dia: nombre, fecha: corto.string(from: fecha), desde: "—", hasta: "", duracion: "",
                                  tipo: "", motivo: "", inicio: "", vacia: true))
            }
            for (i, x) in delDia.enumerated() {
                let m = x["minutos"] as? Int
                let motivo = [x["motivo"] as? String ?? "", x["nota"] as? String ?? ""].filter { !$0.isEmpty }.joined(separator: " · ")
                filas.append(Fila(dia: i == 0 ? nombre : "", fecha: i == 0 ? corto.string(from: fecha) : "",
                                  desde: x["desde"] as? String ?? "", hasta: x["hasta"] as? String ?? "?",
                                  duracion: m.map(f) ?? "?", tipo: x["tipo"] as? String ?? "",
                                  motivo: motivo, inicio: x["inicio"] as? String ?? "", vacia: false))
            }
        }
        let d1 = iso.date(from: dias.first!)!, d2 = iso.date(from: dias.last!)!
        titulo.stringValue = "Semana del \(largo.string(from: d1)) al \(largo.string(from: d2))".replacingOccurrences(of: ".", with: "")
        let t50 = tot["50%"] ?? 0, t100 = tot["100%"] ?? 0
        tarjetaTotal.valor.stringValue = f(t50 + t100)
        tarjeta50.valor.stringValue = f(t50)
        tarjeta100.valor.stringValue = f(t100)
        tabla.reloadData()
    }

    func numberOfRows(in t: NSTableView) -> Int { filas.count }

    func tableView(_ t: NSTableView, viewFor col: NSTableColumn?, row: Int) -> NSView? {
        let fila = filas[row]
        let id = col?.identifier.rawValue ?? ""
        let valor: String
        switch id {
        case "dia": valor = fila.dia
        case "fecha": valor = fila.fecha
        case "desde": valor = fila.desde
        case "hasta": valor = fila.hasta
        case "duracion": valor = fila.duracion
        case "tipo": valor = fila.tipo
        default: valor = fila.vacia ? "" : (fila.motivo.isEmpty ? "Sin justificación" : fila.motivo)
        }
        let campo = NSTextField(labelWithString: valor)
        campo.lineBreakMode = .byTruncatingTail
        campo.textColor = NSColor(white: 0.9, alpha: 1)
        switch id {
        case "dia": campo.font = .systemFont(ofSize: 13, weight: .semibold)
        case "duracion": campo.font = .monospacedDigitSystemFont(ofSize: 14, weight: .bold); campo.textColor = .white
        case "desde", "hasta", "fecha": campo.font = .monospacedDigitSystemFont(ofSize: 13, weight: .regular)
        default: campo.font = .systemFont(ofSize: 13)
        }
        if fila.vacia || (id == "motivo" && fila.motivo.isEmpty) { campo.textColor = NSColor(white: 0.35, alpha: 1) }
        if id == "tipo" && !valor.isEmpty {
            campo.font = .systemFont(ofSize: 11, weight: .bold)
            campo.textColor = Estilo.de(valor == "100%" ? "fuera_sin_marca" : "extra_abierta").fondo
        }
        // Centra verticalmente el texto en la fila alta.
        let celda = NSView()
        campo.translatesAutoresizingMaskIntoConstraints = false
        celda.addSubview(campo)
        NSLayoutConstraint.activate([
            campo.leadingAnchor.constraint(equalTo: celda.leadingAnchor, constant: 4),
            campo.trailingAnchor.constraint(equalTo: celda.trailingAnchor),
            campo.centerYAnchor.constraint(equalTo: celda.centerYAnchor),
        ])
        return celda
    }

    @objc func editarMotivo() {
        let r = tabla.clickedRow
        guard r >= 0, r < filas.count, !filas[r].inicio.isEmpty else { return }
        let f = filas[r]
        guard let m = pedirTexto(titulo: "Justificación", mensaje: "Bloque del \(f.inicio.prefix(10)) desde las \(f.inicio.dropFirst(11).prefix(5)).",
                                 valor: f.motivo, boton: "Guardar"), !m.isEmpty else { return }
        run(["motivo", m, "--bloque", String(f.inicio.prefix(16))])
        cargar()
    }

    func mover(_ dias: Int) {
        dia = Calendar.current.date(byAdding: .day, value: dias, to: dia)!
        cargar()
    }
    @objc func anterior() { mover(-7) }
    @objc func siguiente() { mover(7) }
    @objc func irHoy() { dia = Date(); cargar() }

    func bajar(mes: Bool) {
        let panel = NSSavePanel()
        let base = mes ? "hhcap-mes-\(iso.string(from: dia).prefix(7))" : "hhcap-semana-\(iso.string(from: dia))"
        panel.nameFieldStringValue = base + ".csv"
        panel.allowedContentTypes = [.commaSeparatedText]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        var args = ["reporte", "--fecha", iso.string(from: dia), "-o", url.path]
        if mes { args.append("--mes") }
        let (rc, out) = run(args)
        if rc == 0 { NSWorkspace.shared.activateFileViewerSelecting([url]) }
        else { let a = NSAlert(); a.messageText = "No se pudo descargar"; a.informativeText = out; a.runModal() }
    }
    @objc func bajarSemana() { bajar(mes: false) }
    @objc func bajarMes() { bajar(mes: true) }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
