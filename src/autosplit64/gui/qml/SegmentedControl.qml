import QtQuick
import QtQuick.Controls

// A row of choices with one chosen, the chosen one in the accent color. Like a combo box for a few short choices:
// `model` is a list of texts, `currentIndex` the chosen one, and `activated(index)` is sent as one is clicked.
Rectangle {
    id: root
    property var model: []
    property int currentIndex: -1
    signal activated(int index)

    implicitWidth: row.implicitWidth + 6
    implicitHeight: 32
    radius: Tokens.radiusSmall + 2
    color: Tokens.ground
    border.color: Tokens.line

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2

        Repeater {
            model: root.model
            delegate: AbstractButton {
                id: segment
                required property string modelData
                required property int index
                readonly property bool chosen: index === root.currentIndex
                objectName: root.objectName + "Segment" + index
                text: modelData
                height: root.height - 6
                leftPadding: 10
                rightPadding: 10
                hoverEnabled: true
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                onClicked: {
                    root.currentIndex = index
                    root.activated(index)
                }

                contentItem: Text {
                    text: segment.text
                    font.family: Tokens.fontFamily
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: segment.chosen ? Tokens.accentText : Tokens.muted
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: Tokens.radiusSmall
                    color: segment.chosen ? Tokens.accent : "transparent"
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: Tokens.text
                        opacity: segment.chosen ? 0 : segment.down ? 0.1 : segment.hovered ? 0.05 : 0
                    }
                }
            }
        }
    }
}
