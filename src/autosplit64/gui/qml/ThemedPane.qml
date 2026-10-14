import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material as M
import QtQuick.Controls.Universal as U

// A window's content, in the colors of the app's palette, so the theme setting applies to it: Material's and
// Universal's, and the palette that the other styles draw with, which is otherwise the style's own
Pane {
    padding: 0

    SystemPalette { id: system }
    M.Material.theme: system.window.hslLightness < 0.5 ? M.Material.Dark : M.Material.Light
    M.Material.accent: system.highlight
    M.Material.background: system.window
    M.Material.foreground: system.windowText
    U.Universal.theme: system.window.hslLightness < 0.5 ? U.Universal.Dark : U.Universal.Light
    U.Universal.accent: system.highlight
    U.Universal.background: system.window
    U.Universal.foreground: system.windowText

    // Each group's colors, as a color for all of them would replace the disabled ones whenever it's bound again
    function showPalette() {
        // SystemPalette's: it has no tooltip, link or bright text colors
        const roles = ["window", "windowText", "base", "alternateBase", "text", "button", "buttonText", "highlight",
                       "highlightedText", "light", "midlight", "mid", "dark", "shadow", "placeholderText"]
        for (const role of roles) {
            palette.active[role] = system[role]
            palette.inactive[role] = system[role]
            // The themes' palettes have no disabled colors: text faded like Material's
            palette.disabled[role] = role.endsWith("Text") || role === "text" ? Qt.alpha(system[role], 0.4) : system[role]
        }
    }
    Component.onCompleted: showPalette()
    Connections {
        target: system
        function onPaletteChanged() { showPalette() }
    }
}
