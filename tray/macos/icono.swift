// Genera el ícono de HHCap (cigarrillo encendido) en un .iconset.
// Uso: swift icono.swift <carpeta.iconset>   y luego   iconutil -c icns <carpeta.iconset>
import AppKit

func dibujar(_ lado: CGFloat) -> NSBitmapImageRep {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(lado), pixelsHigh: Int(lado), bitsPerSample: 8,
                               samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                               bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let s = lado / 1024
    let ctx = NSGraphicsContext.current!.cgContext

    // Fondo: squircle oscuro con degradado, margen estándar de íconos macOS.
    let fondo = NSBezierPath(roundedRect: NSRect(x: 100 * s, y: 100 * s, width: 824 * s, height: 824 * s),
                             xRadius: 185 * s, yRadius: 185 * s)
    NSGradient(colors: [NSColor(calibratedRed: 0.17, green: 0.18, blue: 0.22, alpha: 1),
                        NSColor(calibratedRed: 0.06, green: 0.06, blue: 0.08, alpha: 1)])!.draw(in: fondo, angle: -90)

    // Humo: dos volutas suaves saliendo de la brasa.
    ctx.saveGState()
    for (i, alfa) in [(0, 0.55), (1, 0.32)] {
        let p = NSBezierPath()
        let x0 = (700 + CGFloat(i) * 40) * s, y0 = 560 * s
        p.move(to: NSPoint(x: x0, y: y0))
        p.curve(to: NSPoint(x: x0 + 10 * s, y: y0 + 230 * s),
                controlPoint1: NSPoint(x: x0 - 90 * s, y: y0 + 80 * s),
                controlPoint2: NSPoint(x: x0 + 110 * s, y: y0 + 140 * s))
        p.lineWidth = (26 - CGFloat(i) * 8) * s
        p.lineCapStyle = .round
        NSColor(white: 0.85, alpha: alfa).setStroke()
        p.stroke()
    }
    ctx.restoreGState()

    // Cigarrillo en diagonal.
    ctx.saveGState()
    ctx.translateBy(x: 512 * s, y: 470 * s)
    ctx.rotate(by: .pi / 7)
    let largo: CGFloat = 640 * s, alto: CGFloat = 92 * s, x0 = -largo / 2, y0 = -alto / 2
    let filtro: CGFloat = 190 * s, brasa: CGFloat = 46 * s
    // Sombra.
    ctx.setShadow(offset: CGSize(width: 0, height: -14 * s), blur: 30 * s, color: NSColor(white: 0, alpha: 0.6).cgColor)
    NSColor.white.setFill()
    NSBezierPath(roundedRect: NSRect(x: x0, y: y0, width: largo, height: alto), xRadius: 14 * s, yRadius: 14 * s).fill()
    ctx.setShadow(offset: .zero, blur: 0, color: nil)
    // Papel con leve degradado.
    NSGradient(colors: [NSColor(white: 1, alpha: 1), NSColor(white: 0.86, alpha: 1)])!
        .draw(in: NSBezierPath(rect: NSRect(x: x0 + filtro, y: y0, width: largo - filtro - brasa, height: alto)), angle: -90)
    // Filtro corcho con motas.
    let corcho = NSBezierPath(roundedRect: NSRect(x: x0, y: y0, width: filtro, height: alto), xRadius: 14 * s, yRadius: 14 * s)
    NSGradient(colors: [NSColor(calibratedRed: 0.93, green: 0.62, blue: 0.30, alpha: 1),
                        NSColor(calibratedRed: 0.78, green: 0.45, blue: 0.18, alpha: 1)])!.draw(in: corcho, angle: -90)
    NSColor(calibratedRed: 0.62, green: 0.33, blue: 0.12, alpha: 0.55).setFill()
    for (dx, dy) in [(30, 20), (70, 60), (110, 30), (150, 66), (50, 72), (130, 14), (90, 44), (165, 36)] {
        NSBezierPath(ovalIn: NSRect(x: x0 + CGFloat(dx) * s, y: y0 + CGFloat(dy) * s, width: 9 * s, height: 9 * s)).fill()
    }
    NSColor(calibratedRed: 0.85, green: 0.72, blue: 0.40, alpha: 1).setFill()
    NSBezierPath(rect: NSRect(x: x0 + filtro - 10 * s, y: y0, width: 10 * s, height: alto)).fill()
    // Brasa con brillo.
    let rb = NSRect(x: x0 + largo - brasa, y: y0, width: brasa, height: alto)
    ctx.setShadow(offset: .zero, blur: 50 * s, color: NSColor(calibratedRed: 1, green: 0.35, blue: 0.05, alpha: 1).cgColor)
    NSGradient(colors: [NSColor(calibratedRed: 1, green: 0.78, blue: 0.25, alpha: 1),
                        NSColor(calibratedRed: 0.95, green: 0.25, blue: 0.08, alpha: 1),
                        NSColor(calibratedRed: 0.35, green: 0.33, blue: 0.33, alpha: 1)])!
        .draw(in: NSBezierPath(roundedRect: rb, xRadius: 10 * s, yRadius: 10 * s), angle: 0)
    ctx.restoreGState()

    NSGraphicsContext.restoreGraphicsState()
    return rep
}

let salida = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "AppIcon.iconset"
try FileManager.default.createDirectory(atPath: salida, withIntermediateDirectories: true)
for base in [16, 32, 128, 256, 512] {
    for escala in [1, 2] {
        let nombre = escala == 1 ? "icon_\(base)x\(base).png" : "icon_\(base)x\(base)@2x.png"
        let png = dibujar(CGFloat(base * escala)).representation(using: .png, properties: [:])!
        try png.write(to: URL(fileURLWithPath: salida + "/" + nombre))
    }
}
