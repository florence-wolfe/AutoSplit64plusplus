import QtQuick
import QtQuick.Controls as Controls

// The style's Switch, with the pointer over it like the pictures' buttons have, see MainWindow
Controls.Switch {
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
