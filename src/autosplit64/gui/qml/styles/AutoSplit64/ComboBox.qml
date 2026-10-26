import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import "../.." as UI

// A field with a chevron, which opens a panel of rows
T.ComboBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)
    leftPadding: 10
    rightPadding: 10 + indicator.width + spacing
    topPadding: 6
    bottomPadding: 6
    spacing: 6
    font.family: UI.Tokens.fontFamily
    font.pixelSize: 13

    delegate: ItemDelegate {
        required property var model
        required property int index
        width: ListView.view.width
        text: control.textRole ? (Array.isArray(control.model) ? modelData[control.textRole] : model[control.textRole]) : modelData
        highlighted: control.highlightedIndex === index
        hoverEnabled: control.hoverEnabled
    }

    indicator: Shape {
        x: control.width - width - 10
        y: control.topPadding + (control.availableHeight - height) / 2
        width: 12
        height: 12
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: UI.Tokens.muted
            strokeWidth: 1.8
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: "M 2 4.5 L 6 8.5 L 10 4.5" }
        }
    }

    contentItem: T.TextField {
        leftPadding: 0
        rightPadding: 0
        text: control.editable ? control.editText : control.displayText
        enabled: control.editable
        autoScroll: control.editable
        readOnly: control.down
        inputMethodHints: control.inputMethodHints
        validator: control.validator
        selectByMouse: control.selectTextByMouse
        font: control.font
        color: UI.Tokens.text
        selectionColor: UI.Tokens.accent
        selectedTextColor: UI.Tokens.accentText
        verticalAlignment: Text.AlignVCenter
        opacity: control.enabled ? 1 : 0.4
    }

    background: Rectangle {
        implicitWidth: 120
        implicitHeight: 32
        radius: UI.Tokens.radiusSmall
        color: control.hovered || control.down ? Qt.tint(UI.Tokens.ground, Qt.alpha(UI.Tokens.text, 0.06)) : UI.Tokens.ground
        border.width: control.visualFocus || control.popup.visible ? 2 : 1
        border.color: control.visualFocus || control.popup.visible ? UI.Tokens.accent : UI.Tokens.line
        opacity: control.enabled ? 1 : 0.4
    }

    popup: T.Popup {
        y: control.height + 4
        width: control.width
        height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, control.Window.height - topMargin - bottomMargin)
        topMargin: 6
        bottomMargin: 6
        padding: 4

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0
            T.ScrollBar.vertical: ScrollBar {}
        }

        background: Rectangle {
            color: UI.Tokens.panel
            border.color: UI.Tokens.line
            radius: UI.Tokens.radiusRow
        }
    }
}
