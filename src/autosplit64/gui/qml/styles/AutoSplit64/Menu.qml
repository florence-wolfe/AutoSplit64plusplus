import QtQuick
import QtQuick.Templates as T
import "../.." as UI

// A panel with a border and rounded corners, of rows
T.Menu {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, contentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, contentHeight + topPadding + bottomPadding)
    margins: 0
    overlap: 2
    padding: 6

    delegate: MenuItem {}

    contentItem: ListView {
        implicitHeight: contentHeight
        model: control.contentModel
        interactive: Window.window ? contentHeight + control.topPadding + control.bottomPadding > Window.window.height : false
        clip: true
        currentIndex: control.currentIndex
    }

    background: Rectangle {
        implicitWidth: 200
        implicitHeight: 32
        color: UI.Tokens.panel
        border.color: UI.Tokens.line
        radius: UI.Tokens.radiusRow
    }
}
