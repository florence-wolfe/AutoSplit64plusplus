import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material as M

// Shows the tooltips of ToolTip.text, one tooltip for all of a view's QML, to the left of what they're about instead of
// above it. Still above where the view has no room on the left, as tooltips can't leave it.
Item {
    id: root
    SystemPalette { id: system }
    M.Material.theme: system.window.hslLightness < 0.5 ? M.Material.Dark : M.Material.Light

    Component.onCompleted: {
        const tip = ToolTip.toolTip
        const gap = 8
        // Like Material's in the other styles too, as TipWindow is: a popup doesn't take the theme's colors
        tip.palette.toolTipBase = Qt.binding(() => root.M.Material.tooltipColor)
        tip.palette.toolTipText = "white"
        // Implicit sizes, like Material's: Qt narrows a tooltip that doesn't fit when it's placed, which would place it again
        // An item with a `tipAbove` of true, like a row of buttons, has it above, where one to its left would cover the
        // button beside it
        const above = () => tip.parent.tipAbove === true
        const left = () => !above() && tip.parent.mapToItem(null, 0, 0).x - tip.implicitWidth - gap >= tip.margins
        tip.x = Qt.binding(() => !tip.parent ? 0 : left() ? -tip.implicitWidth - gap : (tip.parent.width - tip.implicitWidth) / 2)
        // Material's place above, or closer where it's asked for
        tip.y = Qt.binding(() => !tip.parent ? 0 : left() ? (tip.parent.height - tip.implicitHeight) / 2
                                 : -tip.implicitHeight - (above() ? gap : 24))
    }
}
