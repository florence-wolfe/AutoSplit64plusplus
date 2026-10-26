import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A box that fills with the accent color and a check when it's checked
T.CheckBox {
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
        implicitWidth: 20
        implicitHeight: 20
        radius: 5
        color: control.checkState !== Qt.Unchecked ? UI.Tokens.accent : "transparent"
        opacity: control.enabled ? 1 : 0.4
        border.width: 2
        border.color: control.visualFocus ? UI.Tokens.text : control.checkState !== Qt.Unchecked ? UI.Tokens.accent : UI.Tokens.muted

        UI.CheckIcon {
            anchors.centerIn: parent
            visible: control.checkState === Qt.Checked
            color: UI.Tokens.accentText
        }
        Rectangle {
            anchors.centerIn: parent
            visible: control.checkState === Qt.PartiallyChecked
            width: 10
            height: 2
            radius: 1
            color: UI.Tokens.accentText
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
