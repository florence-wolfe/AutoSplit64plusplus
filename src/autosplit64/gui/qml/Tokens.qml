pragma Singleton
import QtQuick

// The redesign's colors, sizes and type, in one place. The colors are the app palette's roles, so every theme
// applies: AS64++ Dark and Light are made for them, the others follow as well as their palettes allow.
QtObject {
    id: tokens

    readonly property SystemPalette palette: SystemPalette { colorGroup: SystemPalette.Active }

    // The splits' ground, the window and its panels, a raised row, and a border or divider
    readonly property color ground: palette.base
    readonly property color panel: palette.window
    readonly property color raised: palette.mid
    readonly property color line: palette.dark
    readonly property color text: palette.text
    // The text a third of the way to the ground, as theme.muted() has it
    readonly property color muted: Qt.tint(palette.text, Qt.alpha(palette.base, 0.3))
    // The accent, and the text on it
    readonly property color accent: palette.highlight
    readonly property color accentText: palette.highlightedText

    // Corners
    readonly property int radiusSmall: 8
    readonly property int radiusRow: 10
    readonly property int radiusCard: 12

    // Spacing, in steps
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24

    // Type, in pixels
    readonly property int textCaption: 12
    readonly property int textBody: 14
    readonly property int textRow: 15
    readonly property int textTitle: 18
    readonly property int textDisplay: 38
}
