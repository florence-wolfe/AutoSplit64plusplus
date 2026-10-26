import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A button with no fill until it's hovered or pressed
T.ToolButton {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    padding: 6
    spacing: 6
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13
    font.weight: Font.DemiBold

    contentItem: Text {
        text: control.text
        font: control.font
        color: UI.Tokens.text
        opacity: control.enabled ? 1 : 0.4
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: 32
        implicitHeight: 32
        radius: UI.Tokens.radiusSmall
        color: UI.Tokens.text
        opacity: control.down ? 0.14 : control.hovered ? 0.07 : 0
        border.width: control.visualFocus ? 2 : 0
        border.color: UI.Tokens.accent
    }
}
