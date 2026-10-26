import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A raised panel with a border, not the palette's tooltip colors, so a theme's own colors show
T.ToolTip {
    id: control

    x: parent ? (parent.width - implicitWidth) / 2 : 0
    y: -implicitHeight - 3
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, contentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, contentHeight + topPadding + bottomPadding)
    margins: 8
    leftPadding: 10
    rightPadding: 10
    topPadding: 6
    bottomPadding: 6
    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 12

    contentItem: Text {
        text: control.text
        font: control.font
        wrapMode: Text.Wrap
        color: UI.Tokens.text
    }

    background: Rectangle {
        color: UI.Tokens.raised
        border.color: UI.Tokens.line
        radius: UI.Tokens.radiusSmall
    }
}
