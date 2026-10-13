import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Material

// The settings window's content. `settings` is the Python Settings object (settings_dialog.py), which
// holds the values: fields show settings.get() whenever it emits loaded(), and settings.set() their edits.
Pane {
    id: root
    padding: 0

    // Material's controls are sized for touch, even Dense ones: fields and selects are this tall instead
    readonly property int fieldHeight: 32

    // Material's colors from the app's theme, so the theme setting applies here too
    SystemPalette { id: system }
    Material.theme: system.window.hslLightness < 0.5 ? Material.Dark : Material.Light
    Material.accent: system.highlight
    Material.background: system.window
    Material.foreground: system.windowText

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            spacing: 0

            ListView {
                id: nav
                objectName: "nav"
                Layout.fillHeight: true
                Layout.preferredWidth: 190
                topMargin: 8
                model: ["General", "Connection", "Thresholds", "Colour Thresholds", "Error Correction", "Advanced"]
                delegate: ItemDelegate {
                    required property string modelData
                    required property int index
                    width: ListView.view.width
                    text: modelData
                    highlighted: ListView.isCurrentItem
                    onClicked: nav.currentIndex = index
                }
            }

            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: root.Material.dividerColor }

            StackLayout {
                currentIndex: nav.currentIndex
                Layout.fillWidth: true
                Layout.fillHeight: true

                SettingsPage {
                    title: "General"
                    Heading { text: "Startup" }
                    Label { text: "Always on top" }
                    SettingSwitch { section: "general"; key: "on_top" }
                    Label { text: "Check for updates" }
                    SettingSwitch { section: "general"; key: "update_check" }
                    Label { text: "Autostart" }
                    SettingSwitch { section: "general"; key: "auto_start" }

                    Heading { text: "Detection" }
                    Label { text: "Operation mode" }
                    SettingCombo { section: "general"; key: "operation_mode"; model: ["Probability", "X-Cam"] }
                    Label { text: "Allow mid-run starts" }
                    SettingSwitch { section: "general"; key: "mid_run_start_enabled" }
                    Label { text: "Override game version" }
                    RowLayout {
                        SettingSwitch { id: overrideVersion; section: "game"; key: "override_version" }
                        ValueCombo {
                            section: "game"; key: "version"; fallback: "JP"
                            enabled: overrideVersion.checked
                            model: [{ text: "JP", value: "JP" }, { text: "US", value: "US" }]
                        }
                    }

                    Heading { text: "Appearance" }
                    Label { text: "Theme" }
                    ValueCombo {
                        objectName: "theme"
                        section: "general"; key: "theme"; fallback: "default"
                        model: settings.themes
                        Layout.preferredWidth: 200
                        // Shown right away, but only kept when the settings are applied
                        onActivated: settings.show_theme(currentValue)
                    }
                }

                SettingsPage {
                    title: "Connection"
                    Label { text: "Connection mode" }
                    SettingCombo {
                        id: mode
                        objectName: "mode"
                        section: "connection"; key: "ls_connection_type"
                        model: ["Named Pipe", "TCP", "LiveSplit One"]
                        Layout.preferredWidth: 200
                    }
                    // Only the selected mode's settings
                    Label { text: "LiveSplit pipe host"; visible: mode.currentIndex === 0 }
                    SettingField { objectName: "pipeHost"; section: "connection"; key: "ls_pipe_host"; visible: mode.currentIndex === 0 }
                    Label { text: "LiveSplit TCP host"; visible: mode.currentIndex === 1 }
                    SettingField { objectName: "tcpHost"; section: "connection"; key: "ls_host"; visible: mode.currentIndex === 1 }
                    Label { text: "LiveSplit TCP port"; visible: mode.currentIndex === 1 }
                    WholeField { objectName: "tcpPort"; section: "connection"; key: "ls_port"; visible: mode.currentIndex === 1 }
                    Label { text: "LiveSplit One port"; visible: mode.currentIndex === 2 }
                    WholeField { objectName: "lsoPort"; section: "connection"; key: "lso_port"; visible: mode.currentIndex === 2 }
                }

                SettingsPage {
                    title: "Thresholds"
                    columns: 4
                    Heading { text: "Prediction"; Layout.columnSpan: 4 }
                    Label { text: "Probability" }
                    FractionField { section: "thresholds"; key: "probability_threshold" }
                    Label { text: "Reset" }
                    FractionField { section: "thresholds"; key: "reset_threshold" }
                    Label { text: "Confirmation" }
                    FractionField { section: "thresholds"; key: "confirmation_threshold"; Layout.columnSpan: 3 }

                    Heading { text: "Fades"; Layout.columnSpan: 4 }
                    Label { text: "Black" }
                    FractionField { section: "thresholds"; key: "black_threshold" }
                    Label { text: "White" }
                    FractionField { section: "thresholds"; key: "white_threshold" }

                    Heading { text: "X-Cam"; Layout.columnSpan: 4 }
                    Label { text: "B-G threshold" }
                    WholeField { section: "thresholds"; key: "xcam_bg_threshold" }
                    Label { text: "R-G threshold" }
                    WholeField { section: "thresholds"; key: "xcam_rg_threshold" }
                    Label { text: "B-G activation" }
                    WholeField { section: "thresholds"; key: "xcam_bg_activation" }
                    Label { text: "R-G activation" }
                    WholeField { section: "thresholds"; key: "xcam_rg_activation" }
                    Label { text: "Pixel threshold" }
                    FractionField { section: "thresholds"; key: "xcam_pixel_threshold"; Layout.columnSpan: 3 }

                    Heading { text: "Undo"; Layout.columnSpan: 4 }
                    Label { text: "Undo threshold" }
                    FractionField { section: "thresholds"; key: "undo_threshold"; Layout.columnSpan: 3 }
                }

                SettingsPage {
                    title: "Colour Thresholds"
                    Label { text: "Split type" }
                    CompactCombo {
                        id: splitType
                        Layout.preferredWidth: 200
                        model: ["X-Cam", "Mips", "Final Bowser"]
                    }
                    // Colours are stored blue first, like OpenCV's, and shown red first
                    StackLayout {
                        currentIndex: splitType.currentIndex
                        Layout.columnSpan: 2
                        Layout.topMargin: 12
                        ColumnLayout {
                            ColourField { section: "split_xcam"; key: "lower_bound"; label: "Lower bound" }
                            ColourField { section: "split_xcam"; key: "upper_bound"; label: "Upper bound" }
                        }
                        ColumnLayout {
                            ColourField { section: "split_ddd_enter"; key: "portal_lower_bound"; label: "Portal lower bound" }
                            ColourField { section: "split_ddd_enter"; key: "portal_upper_bound"; label: "Portal upper bound" }
                            ColourField { section: "split_ddd_enter"; key: "hat_lower_bound"; label: "Hat lower bound" }
                            ColourField { section: "split_ddd_enter"; key: "hat_upper_bound"; label: "Hat upper bound" }
                        }
                        ColumnLayout {
                            ColourField { section: "split_final_star"; key: "stage_lower_bound"; label: "Stage lower bound" }
                            ColourField { section: "split_final_star"; key: "stage_upper_bound"; label: "Stage upper bound" }
                            ColourField { section: "split_final_star"; key: "star_lower_bound"; label: "Star lower bound" }
                            ColourField { section: "split_final_star"; key: "star_upper_bound"; label: "Star upper bound" }
                        }
                    }
                }

                SettingsPage {
                    title: "Error Correction"
                    Heading { text: "Undo" }
                    Label { text: "Processing length" }
                    WholeField { section: "error"; key: "processing_length" }
                    Label { text: "Undo minimum length" }
                    WholeField { section: "error"; key: "minimum_undo_count" }
                    Label { text: "Undo average threshold" }
                    FractionField { section: "error"; key: "undo_threshold" }

                    Heading { text: "Star skips" }
                    Label { text: "Star skip enabled" }
                    SettingSwitch { section: "error"; key: "star_skip" }
                    Label { text: "Max star skip" }
                    WholeField { section: "error"; key: "max_star_skip" }
                    Label { text: "Consecutive predictions" }
                    WholeField { section: "error"; key: "minimum_consecutive_prediction" }
                }

                SettingsPage {
                    title: "Advanced"
                    Heading { text: "Frames" }
                    Label { text: "File select offset" }
                    SettingSpinBox { section: "advanced"; key: "file_select_frame_offset"; from: -35 }
                    Label { text: "Reset frame one" }
                    PathField { section: "advanced"; key: "reset_frame_one"; title: "Select Reset Frame One" }
                    Label { text: "Reset frame two" }
                    PathField { section: "advanced"; key: "reset_frame_two"; title: "Select Reset Frame Two" }

                    Heading { text: "Frame rates" }
                    Label { text: "Star frame rate" }
                    RateField { section: "advanced"; key: "star_process_frame_rate" }
                    Label { text: "Fadeout frame rate" }
                    RateField { section: "advanced"; key: "fadeout_process_frame_rate" }

                    Heading { text: "Model" }
                    Label { text: "Detection model" }
                    ValueCombo {
                        section: "model"; key: "legacy"; fallback: false
                        Layout.preferredWidth: 240
                        model: [{ text: "AS64+ Star Predictor", value: false }, { text: "AS64 Legacy Model", value: true }]
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.Material.dividerColor }

        RowLayout {
            Layout.margins: 12
            Item { Layout.fillWidth: true }
            Button { text: "Cancel"; flat: true; onClicked: settings.cancel() }
            Button { objectName: "apply"; text: "Apply"; highlighted: true; onClicked: settings.apply() }
        }
    }

    // A page: its title over a grid of label and field columns
    component SettingsPage: ScrollView {
        id: page
        required property string title
        default property alias content: grid.data
        property alias columns: grid.columns
        contentWidth: availableWidth
        padding: 24

        ColumnLayout {
            width: page.availableWidth
            spacing: 8
            Label { text: page.title; font.pixelSize: 22 }
            GridLayout {
                id: grid
                columns: 2
                columnSpacing: 24
                rowSpacing: 4
            }
        }
    }

    component Heading: Label {
        Layout.columnSpan: 2
        Layout.topMargin: 16
        color: root.Material.accent
        font.weight: Font.DemiBold
    }

    component SettingSwitch: Switch {
        id: field
        required property string section
        required property string key
        onToggled: settings.set(section, key, checked)
        Connections { target: settings; function onLoaded() { field.checked = settings.get(field.section, field.key) } }
    }

    // The setting is the chosen item's index
    component SettingCombo: CompactCombo {
        id: field
        required property string section
        required property string key
        onActivated: settings.set(section, key, currentIndex)
        Connections { target: settings; function onLoaded() { field.currentIndex = settings.get(field.section, field.key) } }
    }

    // A choice of { text, value } items, the setting is the chosen one's value, fallback's if it isn't one
    component ValueCombo: CompactCombo {
        id: field
        required property string section
        required property string key
        required property var fallback
        textRole: "text"
        valueRole: "value"
        onActivated: settings.set(section, key, currentValue)
        Connections {
            target: settings
            function onLoaded() {
                const index = field.indexOfValue(settings.get(field.section, field.key))
                field.currentIndex = index >= 0 ? index : field.indexOfValue(field.fallback)
            }
        }
    }

    component CompactField: TextField {
        implicitHeight: root.fieldHeight
        topPadding: 0
        bottomPadding: 0
        verticalAlignment: TextInput.AlignVCenter
    }

    component CompactCombo: ComboBox {
        implicitHeight: root.fieldHeight
    }

    // Only acceptable text is set, see `validator`
    component SettingField: CompactField {
        id: field
        required property string section
        required property string key
        Layout.preferredWidth: 160
        selectByMouse: true
        onTextEdited: if (acceptableInput) settings.set(section, key, text)
        Connections { target: settings; function onLoaded() { field.text = String(settings.get(field.section, field.key)) } }
    }

    component WholeField: SettingField {
        Layout.preferredWidth: 90
        validator: IntValidator { locale: "C" }
    }

    component FractionField: SettingField {
        Layout.preferredWidth: 90
        validator: DoubleValidator { bottom: 0; top: 1; decimals: 3; notation: DoubleValidator.StandardNotation; locale: "C" }
    }

    component RateField: SettingField {
        Layout.preferredWidth: 90
        validator: DoubleValidator { notation: DoubleValidator.StandardNotation; locale: "C" }
    }

    component SettingSpinBox: SpinBox {
        id: field
        implicitHeight: root.fieldHeight
        topPadding: 0
        bottomPadding: 0
        required property string section
        required property string key
        editable: true
        onValueModified: settings.set(section, key, value)
        Connections { target: settings; function onLoaded() { field.value = settings.get(field.section, field.key) } }
    }

    // A file's path, typed or browsed for
    component PathField: RowLayout {
        id: field
        required property string section
        required property string key
        required property string title
        Layout.fillWidth: true
        CompactField {
            id: path
            Layout.fillWidth: true
            selectByMouse: true
            onTextEdited: settings.set_path(field.section, field.key, text)
        }
        Button {
            text: "Browse"
            flat: true
            implicitHeight: root.fieldHeight
            onClicked: {
                const chosen = settings.browse(field.title)
                if (chosen) {
                    path.text = chosen
                    settings.set_path(field.section, field.key, chosen)
                }
            }
        }
        Connections { target: settings; function onLoaded() { path.text = settings.get(field.section, field.key) } }
    }

    component ChannelField: CompactField {
        Layout.preferredWidth: 64
        validator: IntValidator { locale: "C" }
    }

    // A colour's red, green and blue fields
    component ColourField: RowLayout {
        id: field
        required property string section
        required property string key
        required property string label
        spacing: 8

        function save() {
            if (red.acceptableInput && green.acceptableInput && blue.acceptableInput)
                settings.set(section, key, [Number(blue.text), Number(green.text), Number(red.text)])
        }

        Label { text: field.label; Layout.preferredWidth: 150 }
        ChannelField { id: red; placeholderText: "R"; onTextEdited: field.save() }
        ChannelField { id: green; placeholderText: "G"; onTextEdited: field.save() }
        ChannelField { id: blue; placeholderText: "B"; onTextEdited: field.save() }
        Connections {
            target: settings
            function onLoaded() {
                const bgr = settings.get(field.section, field.key)
                blue.text = bgr[0]; green.text = bgr[1]; red.text = bgr[2]
            }
        }
    }
}
