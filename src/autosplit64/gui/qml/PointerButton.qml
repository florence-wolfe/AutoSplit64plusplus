import QtQuick
import QtQuick.Controls as Controls

// The style's Button, with the pointer over it like the pictures' buttons have, see MainWindow
Controls.Button {
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
