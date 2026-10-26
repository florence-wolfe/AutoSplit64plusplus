import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import "../.." as UI

// A field with a chevron above and below at its right, for a step up and down
T.SpinBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)
    leftPadding: 10
    rightPadding: 10 + up.indicator.width
    topPadding: 0
    bottomPadding: 0
    spacing: 0
    editable: true
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13
    validator: IntValidator {
        locale: control.locale.name
        bottom: Math.min(control.from, control.to)
        top: Math.max(control.from, control.to)
    }

    contentItem: TextInput {
        text: control.displayText
        font: control.font
        color: UI.Tokens.text
        selectionColor: UI.Tokens.accent
        selectedTextColor: UI.Tokens.accentText
        selectByMouse: true
        horizontalAlignment: Qt.AlignLeft
        verticalAlignment: Qt.AlignVCenter
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
        opacity: control.enabled ? 1 : 0.4
    }

    up.indicator: Item {
        x: control.mirrored ? 0 : control.width - width
        height: control.height / 2
        implicitWidth: 24
        implicitHeight: 16
        opacity: control.enabled && control.value < control.to ? 1 : 0.3
        Shape {
            anchors.centerIn: parent
            width: 10
            height: 6
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: control.up.pressed || control.up.hovered ? UI.Tokens.text : UI.Tokens.muted
                strokeWidth: 1.6
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: "M 1 5 L 5 1 L 9 5" }
            }
        }
    }

    down.indicator: Item {
        x: control.mirrored ? 0 : control.width - width
        y: control.height - height
        height: control.height / 2
        implicitWidth: 24
        implicitHeight: 16
        opacity: control.enabled && control.value > control.from ? 1 : 0.3
        Shape {
            anchors.centerIn: parent
            width: 10
            height: 6
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "transparent"
                strokeColor: control.down.pressed || control.down.hovered ? UI.Tokens.text : UI.Tokens.muted
                strokeWidth: 1.6
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: "M 1 1 L 5 5 L 9 1" }
            }
        }
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 32
        radius: UI.Tokens.radiusSmall
        color: UI.Tokens.ground
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? UI.Tokens.accent : UI.Tokens.line
        opacity: control.enabled ? 1 : 0.4
    }
}
