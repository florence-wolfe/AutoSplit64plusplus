import QtQuick
import QtQuick.Controls.Material

// A window's content, in Material colors from the app's palette, so the theme setting applies to it
Pane {
    padding: 0

    SystemPalette { id: system }
    Material.theme: system.window.hslLightness < 0.5 ? Material.Dark : Material.Light
    Material.accent: system.highlight
    Material.background: system.window
    Material.foreground: system.windowText
}
