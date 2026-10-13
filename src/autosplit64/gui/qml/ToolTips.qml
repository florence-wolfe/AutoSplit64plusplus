import QtQuick
import QtQuick.Controls.Material

// Shows the tooltips of ToolTip.text, one tooltip for all of a view's QML, to the left of what they're about instead of
// above it. Still above where the view has no room on the left, as tooltips can't leave it.
Item {
    Component.onCompleted: {
        const tip = ToolTip.toolTip
        const gap = 8
        // Implicit sizes, like Material's: Qt narrows a tooltip that doesn't fit when it's placed, which would place it again
        const left = () => tip.parent.mapToItem(null, 0, 0).x - tip.implicitWidth - gap >= tip.margins
        tip.x = Qt.binding(() => !tip.parent ? 0 : left() ? -tip.implicitWidth - gap : (tip.parent.width - tip.implicitWidth) / 2)
        // Material's place above
        tip.y = Qt.binding(() => !tip.parent ? 0 : left() ? (tip.parent.height - tip.implicitHeight) / 2 : -tip.implicitHeight - 24)
    }
}
