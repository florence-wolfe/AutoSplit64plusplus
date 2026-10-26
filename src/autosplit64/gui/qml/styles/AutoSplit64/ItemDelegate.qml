import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A row of a list or a menu: raised when it's highlighted, lighter or darker while hovered or pressed
T.ItemDelegate {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: 12
    rightPadding: 12
    topPadding: 8
    bottomPadding: 8
    spacing: 8
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 14

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.highlighted ? UI.Tokens.text : UI.Tokens.muted
        opacity: control.enabled ? 1 : 0.4
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        implicitHeight: 36
        radius: UI.Tokens.radiusSmall
        color: control.highlighted ? UI.Tokens.raised : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: UI.Tokens.accent

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: UI.Tokens.text
            opacity: control.down ? 0.14 : control.hovered ? 0.07 : 0
        }
    }
}
