import QtQuick
import QtQuick.Templates as T
import "../.." as UI

T.MenuSeparator {
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    verticalPadding: 4

    contentItem: Rectangle {
        implicitWidth: 188
        implicitHeight: 1
        color: UI.Tokens.line
    }
}
