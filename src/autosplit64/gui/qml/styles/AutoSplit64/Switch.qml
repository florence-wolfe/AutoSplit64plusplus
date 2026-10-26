import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A track that takes the accent color when it's on, with a knob that slides along it
T.Switch {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)
    padding: 4
    spacing: 10
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13

    indicator: Rectangle {
        x: control.text ? (control.mirrored ? control.width - width - control.rightPadding : control.leftPadding)
                        : control.leftPadding + (control.availableWidth - width) / 2
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: 40
        implicitHeight: 24
        radius: height / 2
        // Off, the text's color at a quarter: visible on any theme's panel
        color: control.checked ? UI.Tokens.accent : Qt.alpha(UI.Tokens.text, 0.28)
        opacity: control.enabled ? 1 : 0.4
        border.width: control.visualFocus ? 2 : 0
        border.color: UI.Tokens.text
        Behavior on color { ColorAnimation { duration: 120 } }

        Rectangle {
            x: control.checked ? parent.width - width - 3 : 3
            y: 3
            width: parent.height - 6
            height: width
            radius: width / 2
            color: control.checked ? UI.Tokens.accentText : UI.Tokens.muted
            Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 120 } }
        }
    }

    contentItem: Text {
        leftPadding: control.indicator && !control.mirrored ? control.indicator.width + control.spacing : 0
        rightPadding: control.indicator && control.mirrored ? control.indicator.width + control.spacing : 0
        text: control.text
        font: control.font
        color: UI.Tokens.text
        opacity: control.enabled ? 1 : 0.4
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }
}
