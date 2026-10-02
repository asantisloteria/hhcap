.PHONY: test menu icono clean
APP = build/HHCap.app

test:
	python3 -m unittest discover -s tests -v

# HHCap.app: el bundle es necesario para que las notificaciones salgan con el ícono propio.
menu: $(APP)
$(APP): tray/macos/HHCapMenu.swift tray/macos/Info.plist tray/macos/AppIcon.icns
	rm -rf $(APP) && mkdir -p $(APP)/Contents/MacOS $(APP)/Contents/Resources
	swiftc -O tray/macos/HHCapMenu.swift -o $(APP)/Contents/MacOS/hhcap-menu
	cp tray/macos/Info.plist $(APP)/Contents/
	cp tray/macos/AppIcon.icns $(APP)/Contents/Resources/
	codesign --force --sign - $(APP)

# Regenera el ícono (solo si cambia icono.swift).
icono:
	rm -rf build/AppIcon.iconset && mkdir -p build
	swift tray/macos/icono.swift build/AppIcon.iconset
	iconutil -c icns build/AppIcon.iconset -o tray/macos/AppIcon.icns

clean:
	rm -rf build .tmp-*
