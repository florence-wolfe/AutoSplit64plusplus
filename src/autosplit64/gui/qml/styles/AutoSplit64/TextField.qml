import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A field on the splits' ground, with the accent for a border while it has the focus
T.TextField {
    id: control

    implicitWidth: implicitBackgroundWidth + leftInset + rightInset || Math.max(contentWidth + leftPadding + rightPadding, placeholder.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, contentHeight + topPadding + bottomPadding)
    leftPadding: 10
    rightPadding: 10
    topPadding: 6
    bottomPadding: 6
    verticalAlignment: TextInput.AlignVCenter
    selectByMouse: true
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13
    color: UI.Tokens.text
    selectionColor: UI.Tokens.accent
    selectedTextColor: UI.Tokens.accentText
    placeholderTextColor: UI.Tokens.muted
    opacity: enabled ? 1 : 0.4

    Text {
        id: placeholder
        x: control.leftPadding
        y: control.topPadding
        width: control.width - control.leftPadding - control.rightPadding
        height: control.height - control.topPadding - control.bottomPadding
        text: control.placeholderText
        font: control.font
        color: control.placeholderTextColor
        verticalAlignment: control.verticalAlignment
        elide: Text.ElideRight
        visible: !control.length && !control.preeditText
    }

    background: Rectangle {
        implicitWidth: 120
        implicitHeight: 32
        radius: UI.Tokens.radiusSmall
        color: UI.Tokens.ground
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? UI.Tokens.accent : UI.Tokens.line
    }
}
