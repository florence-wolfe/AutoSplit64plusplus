import QtQuick
import QtQuick.Controls.Material as Controls

// Material's Button, with the pointer over it like the pictures' buttons have, see MainWindow
Controls.Button {
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
