import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material as M
import QtQuick.Controls.Universal as U
import QtQuick.Effects
import QtQuick.Shapes

// The main window's content: the route's splits beside the connection, star count and start button. `main` is
// the Python Main object (app.py): its values are what's shown, and its slots the clicks, drags and menu.
ThemedPane {
    id: root

    SystemPalette { id: system; colorGroup: SystemPalette.Active }

    // The menu while it's open, see makeMenu()
    property var openedMenu: null

    // Anywhere else, dragging moves the window and the right button opens the menu
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        function global(mouse) { return mapToGlobal(mouse.x, mouse.y) }
        onPressed: mouse => {
            if (mouse.button === Qt.RightButton)
                root.openMenu(mouse.x, mouse.y)
            // On Windows, pressing a menu entry over the window presses the window too, and moving it would raise
            // it over the menu, which then never gets the click
            else if (root.openedMenu)
                mouse.accepted = false
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

        // The route's name and how far along it is, above the splits
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 239
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 14
                Layout.rightMargin: 12
                Layout.topMargin: 10
                Layout.bottomMargin: 4
                spacing: Tokens.space2

                Label {
                    objectName: "routeTitle"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: main.values.routeTitle
                    color: Tokens.muted
                    font.family: Tokens.fontFamily
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                    font.capitalization: Font.AllUppercase
                    // All of it, where it's cut off
                    HoverHandler { id: routeHover }
                    WindowTip { text: parent.truncated ? parent.text : ""; shown: routeHover.hovered }
                }
                Label {
                    objectName: "splitProgress"
                    text: main.values.current + " of " + main.values.splits.length
                    color: Tokens.muted
                    font.family: Tokens.fontFamily
                    font.pixelSize: Tokens.textBody
                }
            }

            // The splits, as many rows as fit: icon, title and star count, the current one raised, those before it
            // dimmed and checked off
            ListView {
                id: splitList
                objectName: "splitList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // Dragging moves the window instead
                interactive: false
                clip: true
                model: main.values.splits
                currentIndex: main.values.current
                readonly property real rowHeight: height / Math.max(1, Math.floor(height / 40))
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                onHeightChanged: { positionViewAtIndex(currentIndex, ListView.Contain); settleTimer.restart() }
                onCountChanged: settleTimer.restart()

                // Only whole rows are left showing, as the window always had: once a scroll has stopped, the list
                // settles on the nearest row, which at the end is the last split's. The rows are as many as fit, so
                // the end is a whole number of rows too.
                function settle() {
                    const last = Math.max(0, rowHeight * count - height)
                    settleTo.to = Math.max(0, Math.min(Math.round(contentY / rowHeight) * rowHeight, last))
                    settleTo.restart()
                }
                NumberAnimation { id: settleTo; target: splitList; property: "contentY"; duration: 120; easing.type: Easing.OutCubic }
                Timer { id: settleTimer; interval: 150; onTriggered: splitList.settle() }

                delegate: Item {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool current: index === splitList.currentIndex
                    readonly property bool done: index < splitList.currentIndex
                    readonly property real tileSize: height - 12
                    width: ListView.view.width
                    height: splitList.rowHeight

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: Tokens.space2
                        anchors.rightMargin: Tokens.space1
                        anchors.topMargin: 2
                        anchors.bottomMargin: 2
                        radius: Tokens.radiusRow
                        color: row.current ? Tokens.raised : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 8

                            // The split's icon with rounded corners, or its first letters where it has none
                            Item {
                                Layout.preferredWidth: row.tileSize
                                Layout.preferredHeight: row.tileSize
                                opacity: row.done ? 0.45 : 1

                                Image {
                                    id: art
                                    anchors.fill: parent
                                    visible: status === Image.Ready
                                    source: row.modelData.icon || ""
                                    sourceSize.width: width * 2
                                    sourceSize.height: height * 2
                                    fillMode: Image.PreserveAspectCrop
                                    layer.enabled: true
                                    layer.effect: MultiEffect {
                                        maskEnabled: true
                                        maskSource: artMask
                                    }
                                }
                                Item {
                                    id: artMask
                                    anchors.fill: parent
                                    visible: false
                                    layer.enabled: true
                                    Rectangle { anchors.fill: parent; radius: 6 }
                                }
                                Rectangle {
                                    anchors.fill: parent
                                    visible: art.status !== Image.Ready
                                    radius: 6
                                    color: Tokens.line
                                    Label {
                                        anchors.centerIn: parent
                                        text: (row.modelData.title || "").slice(0, 2)
                                        color: Tokens.muted
                                        font.family: Tokens.fontFamily
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }

                            Label {
                                objectName: "splitTitle"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                text: row.modelData.title
                                color: row.done ? Tokens.muted : Tokens.text
                                font.family: Tokens.fontFamily
                                font.pixelSize: Tokens.textRow
                                font.weight: row.current ? Font.DemiBold : Font.Medium
                                // All of it, where it's cut off
                                HoverHandler { id: titleHover }
                                WindowTip { text: parent.truncated ? parent.text : ""; shown: titleHover.hovered }
                            }

                            // What kind of split it is, unless it's a normal one
                            SplitTypeIcon {
                                id: typeIcon
                                objectName: "splitType"
                                visible: ["Fade", "Mips", "Mips-X", "X-Cam", "Final"].indexOf(type) >= 0
                                type: row.modelData.type || ""
                                size: 18
                                color: row.done ? Tokens.muted : Tokens.text
                                HoverHandler { id: typeHover }
                                WindowTip {
                                    text: ({"Fade": "Splits on a fade", "Mips": "Mips", "Mips-X": "Mips, with an X-Cam",
                                            "X-Cam": "Splits on an X-Cam", "Final": "The final split"})[typeIcon.type] || ""
                                    shown: typeHover.hovered
                                }
                            }

                            // Checked off before the star count
                            Item {
                                Layout.preferredWidth: 16
                                Layout.preferredHeight: 16
                                CheckIcon {
                                    objectName: "splitDone"
                                    anchors.centerIn: parent
                                    visible: row.done
                                    color: main.values.green
                                }
                            }
                            // The star count it's at, where it has one: the number right-aligned against the star at
                            // the right edge, the same distance from it as the icon is from the left
                            Item {
                                Layout.preferredWidth: 42
                                Layout.fillHeight: true
                                Row {
                                    objectName: "splitStarBadge"
                                    anchors.right: parent.right
                                    // The star's points are inside its box by 1.5 px
                                    anchors.rightMargin: -1.5
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: !!row.modelData.star
                                    layoutDirection: Qt.RightToLeft
                                    spacing: 4
                                    StarIcon { anchors.verticalCenter: parent.verticalCenter; size: 14; color: Tokens.muted }
                                    Label {
                                        objectName: "splitStar"
                                        text: row.modelData.star || ""
                                        color: Tokens.muted
                                        font.family: Tokens.fontFamily
                                        font.pixelSize: Tokens.textBody
                                    }
                                }
                            }
                        }
                    }
                }

                // Scrolls by the pixels a trackpad moves, or a row for each notch of a wheel, and settles on a row when
                // it stops. Dragging still moves the window, so the list isn't flickable.
                WheelHandler {
                    acceptedDevices: PointerDevice.AllDevices
                    onWheel: event => {
                        const delta = event.pixelDelta.y !== 0 ? event.pixelDelta.y
                                    : event.angleDelta.y / 120 * splitList.rowHeight
                        // Not contentHeight, which is an estimate until the rows are made, and the rows are all the same height
                        const last = Math.max(0, splitList.rowHeight * splitList.count - splitList.height)
                        settleTo.stop()
                        splitList.contentY = Math.max(0, Math.min(last, splitList.contentY - delta))
                        settleTimer.restart()
                    }
                }

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            }
        }

        Rectangle {
            objectName: "divider"
            Layout.fillHeight: true
            implicitWidth: 1
            color: Tokens.line
        }

        // The connection, restart button, star count, start button, version and menu
        Rectangle {
            id: panel
            objectName: "rightPanel"
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            Layout.minimumHeight: 330
            color: Tokens.panel

            // The connection to LiveSplit. Clicking it copies the address.
            Rectangle {
                id: status
                objectName: "status"
                x: 14
                y: 14
                height: 28
                width: Math.min(statusLabel.implicitWidth + 8 + 8 + 24, restart.x - 8 - x)
                radius: height / 2
                color: Tokens.raised
                // "Copied" and the address for a moment once clicked, instead of the status
                property string copied
                Row {
                    id: statusRow
                    anchors.centerIn: parent
                    spacing: 8
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 8
                        height: 8
                        radius: 4
                        color: main.values.statusColor
                    }
                    Label {
                        id: statusLabel
                        objectName: "statusLabel"
                        anchors.verticalCenter: parent.verticalCenter
                        width: Math.min(implicitWidth, status.width - 24 - 16)
                        elide: Text.ElideRight
                        text: main.values.statusLabel
                        color: Tokens.text
                        font.family: Tokens.fontFamily
                        font.pixelSize: Tokens.textCaption
                        font.weight: Font.Medium
                    }
                }
                // The dot's color is the state, which the tooltip also says
                Accessible.name: main.values.statusLabel
                Accessible.description: main.values.statusTip
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

            ActionButton {
                id: restart
                objectName: "restart"
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 10
                anchors.rightMargin: 12
                implicitWidth: 36
                implicitHeight: 36
                fill: "transparent"
                tip: "Restart split detection, which picks up from your timer's current split. The timer itself isn't affected."
                contentItem: Item { ActionIcon { name: "restart"; color: Tokens.muted; anchors.centerIn: parent } }
                onClicked: main.restart()
            }

            // The star count, in a ring that fills as it nears the current split's, and what detection is doing
            ColumnLayout {
                anchors.top: status.bottom
                anchors.bottom: startButton.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 12
                spacing: 12

                Item { Layout.fillHeight: true }

                Item {
                    id: ring
                    objectName: "starRing"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 132
                    Layout.preferredHeight: 132
                    // From 0 to 1: the stars so far of the current split's, none where it has no count
                    readonly property real progress: {
                        const count = Number(main.values.starCount), target = Number(main.values.splitStar)
                        return isFinite(count) && isFinite(target) && target > 0 ? Math.max(0, Math.min(1, count / target)) : 0
                    }
                    property real shown: progress
                    Behavior on shown { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Tokens.line
                            strokeWidth: 8
                            PathAngleArc { centerX: 66; centerY: 66; radiusX: 58; radiusY: 58; startAngle: 0; sweepAngle: 360 }
                        }
                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: ring.shown > 0 ? Tokens.accent : "transparent"
                            strokeWidth: 8
                            capStyle: ShapePath.RoundCap
                            PathAngleArc { centerX: 66; centerY: 66; radiusX: 58; radiusY: 58; startAngle: -90; sweepAngle: 360 * ring.shown }
                        }
                    }
                    Column {
                        anchors.centerIn: parent
                        spacing: 4
                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 6
                            StarIcon { anchors.verticalCenter: parent.verticalCenter; size: 22; color: Tokens.accent }
                            Label {
                                objectName: "starCount"
                                text: main.values.starCount
                                color: Tokens.text
                                font.family: Tokens.fontFamily
                                font.pixelSize: Tokens.textDisplay
                                font.weight: Font.Bold
                            }
                        }
                        Label {
                            objectName: "starTarget"
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: main.values.splitStar === "-" ? "stars" : "of " + main.values.splitStar + " stars"
                            color: Tokens.muted
                            font.family: Tokens.fontFamily
                            font.pixelSize: Tokens.textCaption
                        }
                    }
                }

                Label {
                    objectName: "statusLine"
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: main.values.start === "stop"
                        ? "Detecting" + (main.values.splits[main.values.current] ? " · " + main.values.splits[main.values.current].title : "")
                        : main.values.start === "init" ? "Starting split detection…" : "Split detection is off"
                    color: Tokens.muted
                    font.family: Tokens.fontFamily
                    font.pixelSize: Tokens.textCaption
                }

                Item { Layout.fillHeight: true }
            }

            ActionButton {
                id: startButton
                objectName: "start"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: menuButton.top
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.bottomMargin: 8
                // Starting, or already started, it's a quiet button: the start is what draws the eye
                fill: main.values.start === "start" ? Tokens.accent : Tokens.raised
                tip: ({
                    "start": "Start split detection",
                    "stop": "Stop split detection. Your timer isn't affected, unless Pause timer on stop is on.",
                    "init": "Starting split detection... Click to cancel."
                })[main.values.start]
                contentItem: Item {
                    Row {
                        anchors.centerIn: parent
                        spacing: 8
                        ActionIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: main.values.start === "start" ? "play" : "stop"
                            color: main.values.start === "start" ? Tokens.accentText : Tokens.text
                        }
                        Label {
                            objectName: "startLabel"
                            anchors.verticalCenter: parent.verticalCenter
                            text: ({"start": "Start", "stop": "Stop", "init": "Starting…"})[main.values.start]
                            color: main.values.start === "start" ? Tokens.accentText : Tokens.text
                            font.family: Tokens.fontFamily
                            font.pixelSize: Tokens.textBody
                            font.weight: Font.DemiBold
                        }
                    }
                }
                onClicked: main.start_clicked()
            }

            // The installed version, with a dot when there's an update
            Label {
                objectName: "version"
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: menuButton.verticalCenter
                textFormat: Text.StyledText
                font.family: Tokens.fontFamily
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
                    const corner = menuButton.mapToItem(root, 0, 0)
                    menu.popup(corner.x + menuButton.width - menu.width,
                               Math.max(corner.y - root.menuHeight(menu), main.screen_top() - root.mapToGlobal(0, 0).y))
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
        }
    }

    // The menu's entries come from main.menu(), each time it opens, so routes and checks are current
    function makeMenu() {
        const menu = menuComponent.createObject(root)
        fill(menu, main.menu())
        root.openedMenu = menu
        menu.closed.connect(() => {
            if (root.openedMenu === menu)
                root.openedMenu = null
            menu.destroy()
        })
        return menu
    }

    // Before it opens, when its height isn't known: the entries', the space between them and the padding
    function menuHeight(menu) {
        let height = menu.topPadding + menu.bottomPadding + (menu.contentItem.spacing || 0) * Math.max(menu.count - 1, 0)
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
            // A window that's a popup is made shorter by insets outside it, e.g. the macOS style's for its shadow,
            // and its entries then scroll
            topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
            // As tall as the other entries, see itemComponent: the menu makes those that open submenus
            delegate: MenuItem { implicitHeight: 32 }
            M.Material.theme: root.M.Material.theme
            M.Material.accent: root.M.Material.accent
            M.Material.background: root.M.Material.background
            M.Material.foreground: root.M.Material.foreground
            U.Universal.theme: root.U.Universal.theme
            U.Universal.accent: root.U.Universal.accent
            U.Universal.background: root.U.Universal.background
            U.Universal.foreground: root.U.Universal.foreground
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

    // A button with a tooltip, filled with `fill`, and lighter or darker while hovered or pressed
    component ActionButton: AbstractButton {
        id: button
        property string tip
        property color fill: "transparent"
        implicitHeight: 44
        // Also where the platform has no hover effects
        hoverEnabled: true
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        WindowTip { text: button.tip; shown: button.hovered }
        background: Rectangle {
            radius: Tokens.radiusCard
            color: button.fill
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: Tokens.text
                opacity: button.pressed ? 0.14 : button.hovered ? 0.07 : 0
            }
        }
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
