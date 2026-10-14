import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material as M

// The main window's content: the route's splits beside the star, star count and start button, which keep
// their art. `main` is the Python Main object (app.py): its values are what's shown, and its slots the
// clicks, drags and menu. `art` has the pictures' URLs.
ThemedPane {
    id: root

    SystemPalette { id: system; colorGroup: SystemPalette.Active }

    // Anywhere else, dragging moves the window and the right button opens the menu
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        function global(mouse) { return mapToGlobal(mouse.x, mouse.y) }
        onPressed: mouse => {
            if (mouse.button === Qt.RightButton)
                root.openMenu(mouse.x, mouse.y)
            else {
                const point = global(mouse)
                main.press(point.x, point.y)
            }
        }
        onPositionChanged: mouse => {
            const point = global(mouse)
            main.drag(point.x, point.y)
        }
        onReleased: main.release()
    }

    Rectangle { anchors.fill: parent; color: system.base; z: -1 }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // The splits, as many rows as fit, the current one highlighted
        ListView {
            id: splitList
            objectName: "splitList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 183
            // Dragging moves the window instead
            interactive: false
            clip: true
            model: main.values.splits
            currentIndex: main.values.current
            readonly property real rowHeight: height / Math.max(1, Math.floor(height / 37))
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            onHeightChanged: positionViewAtIndex(currentIndex, ListView.Contain)

            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width
                height: splitList.rowHeight
                // Alternating shades of the background, and the theme's highlight for the current split,
                // also while another window has focus, as during a run
                color: index === splitList.currentIndex ? system.highlight
                     : Qt.darker(system.base, index % 2 ? 1.08 : 1.03)

                Image {
                    x: (parent.height - width) / 2
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.height * 0.8
                    height: width
                    source: modelData.icon
                    sourceSize.width: width
                    sourceSize.height: height
                }
                Label {
                    x: parent.height
                    width: parent.width - x
                    height: parent.height
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    text: modelData.title
                    color: system.text
                    font.family: "Tw Cen MT"
                    font.pointSize: 14
                }
            }

            // A row at a time, like the window did before
            WheelHandler {
                property real steps: 0
                onWheel: event => {
                    steps += event.angleDelta.y
                    if (Math.abs(steps) < 120)
                        return
                    const first = splitList.indexAt(0, splitList.contentY + 1) + (steps > 0 ? -1 : 1)
                    steps = 0
                    splitList.positionViewAtIndex(Math.max(0, Math.min(first, splitList.count - 1)), ListView.Beginning)
                }
            }
        }

        // The star, star count and start button, at their places in the art's panel
        Item {
            objectName: "rightPanel"
            Layout.preferredWidth: 182
            Layout.preferredHeight: 259
            Layout.alignment: Qt.AlignVCenter

            ArtButton {
                objectName: "star"
                x: 59
                y: 35
                normal: art.star
                hover: art.starHover
                tip: "Restart split detection, which picks up from your timer's current split. The timer itself isn't affected."
                onClicked: main.restart()
            }

            Label {
                objectName: "starCount"
                x: 14
                y: 115
                width: 150
                horizontalAlignment: Text.AlignHCenter
                text: main.values.starCount + "  /  " + main.values.splitStar
                color: system.text
                font.family: "Tw Cen MT"
                font.pointSize: 20
            }

            ArtButton {
                objectName: "start"
                x: 23
                y: 180
                normal: art[main.values.start]
                hover: art[main.values.start]
                tip: ({
                    "start": "Start split detection",
                    "stop": "Stop split detection. Your timer isn't affected.",
                    "init": "Starting split detection... Click to cancel."
                })[main.values.start]
                // 10% larger while hovered, around its center
                scale: hovered ? 1.1 : 1
                onClicked: main.start_clicked()
            }
        }
    }

    // The connection to LiveSplit, in the top right corner. Clicking it copies the address.
    Rectangle {
        id: status
        objectName: "status"
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 6
        width: 12
        height: 12
        radius: 6
        color: main.values.statusColor
        border.color: system.dark
        // "Copied" and the address for a moment once clicked, instead of the status
        property string copied
        HoverHandler { id: statusHover; cursorShape: Qt.PointingHandCursor }
        WindowTip { id: statusTip; text: status.copied || main.values.statusTip; shown: statusHover.hovered || status.copied !== "" }
        TapHandler {
            onTapped: {
                status.copied = "Copied " + main.copy_status()
                statusTip.open()
                copiedTimer.restart()
            }
        }
        Timer { id: copiedTimer; interval: 2500; onTriggered: status.copied = "" }
    }

    // The installed version, with a dot when there's an update, at the bottom left of the right panel
    Label {
        objectName: "version"
        anchors.right: parent.right
        anchors.rightMargin: 182 - 8 - width
        anchors.verticalCenter: menuButton.verticalCenter
        textFormat: Text.StyledText
        font.pixelSize: 11
        text: "<font color='" + main.values.muted + "'>" + main.values.version + "</font>"
            + (main.values.update ? " <font color='" + main.values.green + "'>●</font>" : "")
        HoverHandler { id: versionHover; cursorShape: Qt.PointingHandCursor }
        WindowTip { text: main.values.versionTip; shown: versionHover.hovered }
        TapHandler { onTapped: main.version_clicked() }
    }

    // The menu, opening upwards from the bottom right corner
    ToolButton {
        id: menuButton
        objectName: "menuButton"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 2
        width: 32
        height: 32
        // Also where the platform has no hover effects
        hoverEnabled: true
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        WindowTip { text: "Menu"; shown: menuButton.hovered }
        onClicked: {
            const menu = root.makeMenu()
            // Above the button, but not above the screen: Qt doesn't keep a popup that's a window on it. Where
            // it opens, not after, which would show it below the button first.
            menu.popup(menuButton.x + menuButton.width - menu.width,
                       Math.max(menuButton.y - root.menuHeight(menu), main.screen_top() - root.mapToGlobal(0, 0).y))
        }
        // Three lines, centered
        contentItem: Item {
            Column {
                anchors.centerIn: parent
                spacing: 3
                Repeater {
                    model: 3
                    Rectangle {
                        width: 14
                        height: 2
                        radius: 1
                        color: menuButton.hovered ? system.text : main.values.muted
                    }
                }
            }
        }
    }

    // The menu's entries come from main.menu(), each time it opens, so routes and checks are current
    function makeMenu() {
        const menu = menuComponent.createObject(root)
        fill(menu, main.menu())
        menu.closed.connect(() => menu.destroy())
        return menu
    }

    // Before it opens, when its height isn't known: the entries' and the padding
    function menuHeight(menu) {
        let height = menu.topPadding + menu.bottomPadding
        for (let i = 0; i < menu.count; i++)
            height += menu.itemAt(i).implicitHeight
        return height
    }

    function openMenu(x, y) {
        makeMenu().popup(x, y)
    }

    function fill(menu, items) {
        for (const item of items) {
            if (item.separator)
                menu.addItem(separatorComponent.createObject(menu.contentItem))
            else if (item.items) {
                const submenu = menuComponent.createObject(menu, { title: item.text })
                fill(submenu, item.items)
                menu.addMenu(submenu)
            } else
                menu.addItem(itemComponent.createObject(menu.contentItem, {
                    text: item.text, key: item.key, tip: item.tooltip, checkable: !!item.checkable, checked: !!item.checked
                }))
        }
    }

    // A window of its own, as it's taller than the main window. Which doesn't take the theme's colors.
    Component {
        id: menuComponent
        Menu {
            popupType: Popup.Window
            // As tall as the other entries, see itemComponent: the menu makes those that open submenus
            delegate: MenuItem { implicitHeight: 32 }
            M.Material.theme: root.M.Material.theme
            M.Material.accent: root.M.Material.accent
            M.Material.background: root.M.Material.background
            M.Material.foreground: root.M.Material.foreground
            palette: root.palette
        }
    }

    Component {
        id: itemComponent
        // Material's are sized for touch, like CompactField's controls
        MenuItem {
            implicitHeight: 32
            property string key
            property string tip
            onTriggered: main.trigger(key)
            HoverHandler { cursorShape: Qt.PointingHandCursor }
            // Beside the menu: it's a window, which a ToolTip can't leave
            WindowTip { text: parent.tip; shown: parent.hovered }
        }
    }

    Component {
        id: separatorComponent
        MenuSeparator { verticalPadding: 2 }
    }

    // A picture, another while hovered
    component ArtButton: AbstractButton {
        id: button
        property url normal
        property url hover
        property string tip
        implicitWidth: picture.implicitWidth
        implicitHeight: picture.implicitHeight
        // Also where the platform has no hover effects: the art changes and grows
        hoverEnabled: true
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        WindowTip { text: button.tip; shown: button.hovered }
        contentItem: Image { id: picture; source: button.hovered || button.pressed ? button.hover : button.normal }
        background: null
    }

    // A tooltip about the item it's in, after the mouse rests on it a moment. It's in `tips`, a window of its own
    // (tip_window.py): to the left also of what's at the window's left edge, or in the menu, which is a window too.
    component WindowTip: Item {
        id: tip
        property string text
        property bool shown
        anchors.fill: parent

        function open() {
            const corner = parent.mapToGlobal(0, 0)
            tips.show(text, corner.x, corner.y, parent.width, parent.height)
        }

        Timer { id: delay; interval: 600; onTriggered: tip.open() }
        onShownChanged: {
            if (shown && text)
                delay.restart()
            else {
                delay.stop()
                tips.hide()
            }
        }
        // e.g. the status changing while it's shown
        onTextChanged: if (shown && text && !delay.running) open()
        // e.g. the menu closing under the mouse
        Component.onDestruction: if (shown) tips.hide()
    }
}
