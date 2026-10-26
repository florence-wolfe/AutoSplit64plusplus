import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// Three levels: an accent-filled button for what a window is for, a raised one with a border for the other things to
// do, and a flat one with no fill or border for the quiet ones, like a toolbar's. Lighter or darker while hovered or
// pressed, in the text's color so it shows in light and dark themes alike.
T.Button {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: 14
    rightPadding: 14
    topPadding: 6
    bottomPadding: 6
    spacing: 8
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13
    font.weight: Font.DemiBold

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.highlighted ? UI.Tokens.accentText : UI.Tokens.text
        opacity: control.enabled ? 1 : 0.4
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitHeight: 32
        radius: UI.Tokens.radiusSmall
        color: control.flat ? "transparent" : control.highlighted ? UI.Tokens.accent : UI.Tokens.raised
        opacity: control.enabled ? 1 : 0.4
        border.width: control.visualFocus ? 2 : control.flat || control.highlighted ? 0 : 1
        border.color: control.visualFocus ? UI.Tokens.accent : Qt.alpha(UI.Tokens.text, 0.2)

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: control.highlighted ? UI.Tokens.accentText : UI.Tokens.text
            opacity: control.down ? 0.14 : control.hovered ? 0.07 : 0
        }
    }
}
