.PHONY: test menu clean
test:
	python3 -m unittest discover -s tests -v
menu: build/hhcap-menu
build/hhcap-menu: tray/macos/HHCapMenu.swift
	mkdir -p build && swiftc -O $< -o $@
clean:
	rm -rf build .tmp-test
