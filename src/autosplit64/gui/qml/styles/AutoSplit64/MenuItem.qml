import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import "../.." as UI

// A row of a menu: a check where it can be checked, an arrow where it opens another menu
T.MenuItem {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)
    leftPadding: 12
    rightPadding: 12
    topPadding: 6
    bottomPadding: 6
    spacing: 8
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13

    arrow: Shape {
        x: control.width - width - control.rightPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        width: 8
        height: 12
        visible: control.subMenu
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: UI.Tokens.muted
            strokeWidth: 1.6
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: "M 1.5 1.5 L 6 6 L 1.5 10.5" }
        }
    }

    // A box, which fills with the accent color and a check when it's checked
    indicator: Rectangle {
        x: control.mirrored ? control.width - width - control.rightPadding : control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: 16
        implicitHeight: 16
        radius: 4
        visible: control.checkable
        color: control.checked ? UI.Tokens.accent : "transparent"
        border.width: 1.5
        border.color: control.checked ? UI.Tokens.accent : UI.Tokens.muted

        UI.CheckIcon {
            anchors.centerIn: parent
            visible: control.checked
            scale: 0.8
            color: UI.Tokens.accentText
        }
    }

    contentItem: Text {
        leftPadding: control.checkable && !control.mirrored ? control.indicator.width + control.spacing : 0
        rightPadding: control.subMenu && !control.mirrored ? control.arrow.width + control.spacing : 0
        text: control.text
        font: control.font
        color: UI.Tokens.text
        opacity: control.enabled ? 1 : 0.4
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        implicitHeight: 32
        x: 2
        width: control.width - 4
        radius: 6
        color: UI.Tokens.text
        opacity: control.down ? 0.14 : control.highlighted ? 0.09 : 0
    }
}
