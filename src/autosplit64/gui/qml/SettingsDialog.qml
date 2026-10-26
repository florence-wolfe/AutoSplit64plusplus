import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material as M

// The settings window's content. `settings` is the Python Settings object (settings_dialog.py), which
// holds the values: fields show settings.get() whenever it emits loaded(), and settings.set() their edits.
ThemedPane {
    id: root

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

            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: root.M.Material.dividerColor }

            StackLayout {
                currentIndex: nav.currentIndex
                Layout.fillWidth: true
                Layout.fillHeight: true

                SettingsPage {
                    title: "General"
                    Heading { text: "Startup" }
                    SettingLabel { text: "Always on top"; tip: "Keep AutoSplit64++'s window above other windows" }
                    SettingSwitch { section: "general"; key: "on_top" }
                    SettingLabel { text: "Check for updates"; tip: "Look for a new version of AutoSplit64++ when it opens" }
                    SettingSwitch { section: "general"; key: "update_check" }
                    SettingLabel { text: "Autostart"; tip: "Start split detection when AutoSplit64++ opens, trying for up to 5 minutes" }
                    SettingSwitch { section: "general"; key: "auto_start" }
                    SettingLabel {
                        text: "Pause timer on stop"
                        tip: "Pause the timer when you click Stop while connected to LiveSplit. Split detection stopping "
                             + "for any other reason, like an error, leaves the timer running"
                    }
                    SettingSwitch { section: "general"; key: "pause_on_stop" }

                    Heading { text: "Detection" }
                    SettingLabel {
                        objectName: "operationModeLabel"
                        text: "Operation mode"
                        tip: "How a collected star is counted:"
                             + "<ul><li><b>Probability</b> (the default): a star counts when the star-count model reads "
                             + "one more star on two looks in a row. One look has to be as sure as the Probability "
                             + "threshold and the other as sure as the Confirmation threshold.</li>"
                             + "<li><b>X-Cam</b>: a star only counts when the model reads one more within 1 s of seeing "
                             + "the camera icon's red X, as Mario collects a star. One look only has to be as sure as "
                             + "the Confirmation threshold.</li></ul>"
                             + "So X-Cam mode is stricter about <i>when</i> a star can count, but not about how sure "
                             + "the reading has to be. Most people should leave it on Probability."
                    }
                    SettingCombo { section: "general"; key: "operation_mode"; model: ["Probability", "X-Cam"] }
                    SettingLabel {
                        text: "Allow mid-run starts"
                        tip: "Pick up a run when the star count shows any star from the previous split's to the current "
                             + "split's, not only the expected one, e.g. when detection starts mid-run"
                    }
                    SettingSwitch { section: "general"; key: "mid_run_start_enabled" }
                    SettingLabel {
                        text: "Override game version"
                        tip: "Read the star count and lives where this version's HUD shows them, instead of where the route's version does"
                    }
                    RowLayout {
                        SettingSwitch { id: overrideVersion; section: "game"; key: "override_version" }
                        ValueCombo {
                            section: "game"; key: "version"; fallback: "JP"
                            enabled: overrideVersion.checked
                            model: [{ text: "JP", value: "JP" }, { text: "US", value: "US" }]
                        }
                    }

                    Heading { text: "Appearance" }
                    SettingLabel { text: "Theme"; tip: "The colours of AutoSplit64++'s windows" }
                    ValueCombo {
                        objectName: "theme"
                        section: "general"; key: "theme"; fallback: "default"
                        model: settings.themes
                        Layout.preferredWidth: 200
                        // Shown right away, but only kept when the settings are applied
                        onActivated: settings.show_theme(currentValue)
                    }
                    SettingLabel { text: "Style"; tip: "The look of AutoSplit64++'s buttons, fields and other controls" }
                    ValueCombo {
                        id: style
                        objectName: "style"
                        section: "general"; key: "style"; fallback: "Material"
                        model: settings.styles
                        Layout.preferredWidth: 200
                    }
                    Item {}
                    Label {
                        objectName: "styleRestart"
                        text: "<font color='" + settings.warningColor + "'>⚠</font> Requires restart"
                        textFormat: Text.StyledText
                        opacity: 0.7
                    }
                    Item { visible: styleAbout.visible }
                    Label {
                        id: styleAbout
                        objectName: "styleAbout"
                        text: style.currentIndex >= 0 ? style.model[style.currentIndex].about : ""
                        visible: text !== ""
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        Layout.preferredWidth: 360
                    }
                }

                SettingsPage {
                    title: "Connection"
                    SettingLabel {
                        text: "Connection mode"
                        tip: "How splits reach LiveSplit. Named Pipe needs nothing started, TCP needs LiveSplit's server "
                             + "started, and LiveSplit One connects to AutoSplit64++ itself."
                    }
                    SettingCombo {
                        id: mode
                        objectName: "mode"
                        section: "connection"; key: "ls_connection_type"
                        model: ["Named Pipe", "TCP", "LiveSplit One"]
                        Layout.preferredWidth: 200
                    }
                    // Only the selected mode's settings
                    SettingLabel {
                        text: "LiveSplit pipe host"; visible: mode.currentIndex === 0
                        tip: "The computer LiveSplit runs on, by name: . for this one"
                    }
                    SettingField { objectName: "pipeHost"; section: "connection"; key: "ls_pipe_host"; visible: mode.currentIndex === 0 }
                    SettingLabel {
                        text: "LiveSplit TCP host"; visible: mode.currentIndex === 1
                        tip: "The address of the computer LiveSplit's server runs on: localhost for this one"
                    }
                    SettingField { objectName: "tcpHost"; section: "connection"; key: "ls_host"; visible: mode.currentIndex === 1 }
                    SettingLabel {
                        text: "LiveSplit TCP port"; visible: mode.currentIndex === 1
                        tip: "The port of LiveSplit's server, as set in LiveSplit's settings: 16834 unless changed"
                    }
                    WholeField { objectName: "tcpPort"; section: "connection"; key: "ls_port"; visible: mode.currentIndex === 1 }
                    SettingLabel {
                        text: "LiveSplit One port"; visible: mode.currentIndex === 2
                        tip: "The port AutoSplit64++ waits for LiveSplit One on: in LiveSplit One, Settings > Connect to "
                             + "Server, ws://localhost:<port>"
                    }
                    WholeField { objectName: "lsoPort"; section: "connection"; key: "lso_port"; visible: mode.currentIndex === 2 }
                }

                SettingsPage {
                    title: "Thresholds"
                    columns: 4
                    Heading { text: "Prediction"; Layout.columnSpan: 4 }
                    SettingLabel {
                        text: "Probability"
                        tip: "How sure, from 0 to 1, the star count model must be of what it reads: of one more star "
                             + "to count it (with Confirmation), of the star count to start a run, and of a star "
                             + "count to skip to"
                    }
                    FractionField { section: "thresholds"; key: "probability_threshold" }
                    SettingLabel {
                        text: "Reset"
                        tip: "How unlike the reset templates, from 0 (identical) to 1, the screen's centre can be "
                             + "and still be a console reset. Higher spots more resets, and mistakes more for one."
                    }
                    FractionField { section: "thresholds"; key: "reset_threshold" }
                    SettingLabel {
                        text: "Confirmation"
                        tip: "How sure, from 0 to 1, the star count model must be of one more star on the look "
                             + "before or after the one as sure as Probability, or in X-Cam mode, on one look"
                    }
                    FractionField { section: "thresholds"; key: "confirmation_threshold"; Layout.columnSpan: 3 }

                    Heading { text: "Fades"; Layout.columnSpan: 4 }
                    SettingLabel {
                        text: "Black"
                        tip: "The brightness, from 0 to 1, below which a pixel is black: a fadeout is when 90% of "
                             + "the star count's and lives' pixels are"
                    }
                    FractionField { section: "thresholds"; key: "black_threshold" }
                    SettingLabel {
                        text: "White"
                        tip: "The brightness, from 0 to 1, above which a pixel is white: a fade to white is when 99% "
                             + "of the star count's and lives' pixels are"
                    }
                    FractionField { section: "thresholds"; key: "white_threshold" }

                    Heading { text: "X-Cam"; Layout.columnSpan: 4 }
                    SettingLabel {
                        text: "B-G threshold"
                        tip: "A pixel whose green and blue differ by more than this, from 0 to 255, isn't the camera "
                             + "icon's red X, if its green is above B-G activation"
                    }
                    WholeField { section: "thresholds"; key: "xcam_bg_threshold" }
                    SettingLabel {
                        text: "R-G threshold"
                        tip: "A pixel whose red and green differ by less than this, from 0 to 255, isn't the camera "
                             + "icon's red X, if its green is above R-G activation"
                    }
                    WholeField { section: "thresholds"; key: "xcam_rg_threshold" }
                    SettingLabel {
                        text: "B-G activation"
                        tip: "The green, from 0 to 255, above which B-G threshold applies to a pixel"
                    }
                    WholeField { section: "thresholds"; key: "xcam_bg_activation" }
                    SettingLabel {
                        text: "R-G activation"
                        tip: "The green, from 0 to 255, above which R-G threshold applies to a pixel"
                    }
                    WholeField { section: "thresholds"; key: "xcam_rg_activation" }
                    SettingLabel {
                        text: "Pixel threshold"
                        tip: "The share, from 0 to 1, of the camera icon's pixels that must be its red X for the X-Cam "
                             + "to show, as when Mario collects a star"
                    }
                    FractionField { section: "thresholds"; key: "xcam_pixel_threshold"; Layout.columnSpan: 3 }

                    Heading { text: "Undo"; Layout.columnSpan: 4 }
                    SettingLabel {
                        text: "Undo threshold"
                        tip: "Seconds: a console reset this soon after a split undoes that split, unless in SRL mode"
                    }
                    FractionField { section: "thresholds"; key: "undo_threshold"; Layout.columnSpan: 3 }
                }

                SettingsPage {
                    title: "Colour Thresholds"
                    SettingLabel {
                        text: "Split type"
                        tip: "Whose colours to edit. A pixel is one of them when its red, green and blue are each "
                             + "from the lower bound's to the upper bound's, from 0 to 255."
                    }
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
                            ColourField {
                                section: "split_xcam"; key: "lower_bound"; label: "Lower bound"
                                tip: "The darkest colours of the camera icon's red X, shown as Mario collects a star"
                            }
                            ColourField {
                                section: "split_xcam"; key: "upper_bound"; label: "Upper bound"
                                tip: "The brightest colours of the camera icon's red X, shown as Mario collects a star"
                            }
                        }
                        ColumnLayout {
                            ColourField {
                                section: "split_ddd_enter"; key: "portal_lower_bound"; label: "Portal lower bound"
                                tip: "The darkest colours of the DDD painting's portal: once it shows, the split waits for Mario's hat to go"
                            }
                            ColourField {
                                section: "split_ddd_enter"; key: "portal_upper_bound"; label: "Portal upper bound"
                                tip: "The brightest colours of the DDD painting's portal: once it shows, the split waits for Mario's hat to go"
                            }
                            ColourField {
                                section: "split_ddd_enter"; key: "hat_lower_bound"; label: "Hat lower bound"
                                tip: "The darkest colours of Mario's hat: it splits on the first frame without them, or with AS64++ Detection, once they drop out of sight at once"
                            }
                            ColourField {
                                section: "split_ddd_enter"; key: "hat_upper_bound"; label: "Hat upper bound"
                                tip: "The brightest colours of Mario's hat: it splits on the first frame without them, or with AS64++ Detection, once they drop out of sight at once"
                            }
                        }
                        ColumnLayout {
                            ColourField {
                                section: "split_final_star"; key: "stage_lower_bound"; label: "Stage lower bound"
                                tip: "The darkest colours of Bowser's last stage: once it shows, the Grand Star is looked for"
                            }
                            ColourField {
                                section: "split_final_star"; key: "stage_upper_bound"; label: "Stage upper bound"
                                tip: "The brightest colours of Bowser's last stage: once it shows, the Grand Star is looked for"
                            }
                            ColourField {
                                section: "split_final_star"; key: "star_lower_bound"; label: "Star lower bound"
                                tip: "The darkest colours of the Grand Star's yellow"
                            }
                            ColourField {
                                section: "split_final_star"; key: "star_upper_bound"; label: "Star upper bound"
                                tip: "The brightest colours of the Grand Star's yellow"
                            }
                        }
                    }
                }

                SettingsPage {
                    title: "Error Correction"
                    Heading { text: "Undo" }
                    SettingLabel {
                        text: "Processing length"
                        tip: "How many of the star count model's latest reads are kept, to tell if a star was miscounted"
                    }
                    WholeField { section: "error"; key: "processing_length" }
                    SettingLabel {
                        text: "Undo minimum length"
                        tip: "How many of those reads must be of one star fewer before the star count can go back down"
                    }
                    WholeField { section: "error"; key: "minimum_undo_count" }
                    SettingLabel {
                        text: "Undo average threshold"
                        tip: "How sure on average, from 0 to 1, those reads of one star fewer must be to take the star "
                             + "back, and undo its split if it split"
                    }
                    FractionField { section: "error"; key: "undo_threshold" }

                    Heading { text: "Star skips" }
                    SettingLabel {
                        text: "Star skip enabled"
                        tip: "Let the star count jump straight to what the model keeps reading, up to the next "
                             + "split's star, e.g. after it missed a star"
                    }
                    SettingSwitch { section: "error"; key: "star_skip" }
                    SettingLabel { text: "Max star skip"; tip: "The most stars the star count can jump by, up or down" }
                    WholeField { section: "error"; key: "max_star_skip" }
                    SettingLabel {
                        text: "Consecutive predictions"
                        tip: "How many reads in a row must agree on a star count, each as sure as the Probability "
                             + "threshold, before it's jumped to"
                    }
                    WholeField { section: "error"; key: "minimum_consecutive_prediction" }
                }

                SettingsPage {
                    title: "Advanced"
                    Heading { text: "Frames" }
                    SettingLabel {
                        objectName: "fileSelectOffsetLabel"
                        text: "File select offset"
                        tip: "For routes timed from File Select: frames, at 30 fps, added to the 1.2 s wait between "
                             + "choosing the file and the split. Negative splits sooner."
                    }
                    SettingSpinBox { section: "advanced"; key: "file_select_frame_offset"; from: -35 }
                    SettingLabel {
                        text: "Reset frame one"
                        tip: "A picture of the screen's centre as the console resets, to spot resets by. Generate "
                             + "Reset Templates makes it from your capture."
                    }
                    PathField { section: "advanced"; key: "reset_frame_one"; title: "Select Reset Frame One" }
                    SettingLabel {
                        text: "Reset frame two"
                        tip: "Another picture of the screen's centre as the console resets, to spot resets by. "
                             + "Generate Reset Templates makes it from your capture."
                    }
                    PathField { section: "advanced"; key: "reset_frame_two"; title: "Select Reset Frame Two" }

                    Heading { text: "Frame rates" }
                    SettingLabel {
                        text: "Star frame rate"
                        tip: "How many times a second the star count is read in a level. Higher counts stars sooner, "
                             + "with more CPU."
                    }
                    RateField { section: "advanced"; key: "star_process_frame_rate" }
                    SettingLabel {
                        text: "Fadeout frame rate"
                        tip: "How many times a second the screen is looked at during a fadeout, to split and spot resets"
                    }
                    RateField { section: "advanced"; key: "fadeout_process_frame_rate" }

                    Heading { text: "Model" }
                    SettingLabel {
                        text: "Detection model"
                        tip: "What reads the star count and finds the Mips and final splits. What each does is shown below it."
                    }
                    ValueCombo {
                        id: detectionModel
                        objectName: "detectionModel"
                        section: "model"; key: "detection"; fallback: "star_predictor"
                        Layout.preferredWidth: 240
                        model: [
                            { text: "AS64++ Detection", value: "as64pp",
                              about: "The AS64+ Star Predictor, with new Mips and final splits. It only looks for the Grand Star "
                                     + "once Bowser gave his last speech, so yellow in the fight, from Bowser or the "
                                     + "power meter, can't split it before he's beaten, which some captures and "
                                     + "emulators did with the others. It splits on the first frame after Mario grabs it. "
                                     + "Mips splits once Mario's hat drops out of sight at once, as he enters the painting, "
                                     + "not as it fades while he's far and in shadow, or before he's in sight after the door clip." },
                            { text: "AS64+ Star Predictor", value: "star_predictor",
                              about: "AutoSplit64+'s star predictor. The final split looks for the Grand Star's yellow "
                                     + "from 20 s into the fight, and can split early when Bowser or the power meter "
                                     + "shows it for long enough." },
                            { text: "AS64 Legacy Model", value: "legacy",
                              about: "AutoSplit64's original star predictor, with the final split of the AS64+ Star Predictor." }
                        ]
                    }
                    Item {}
                    Label {
                        objectName: "detectionModelAbout"
                        text: detectionModel.currentIndex >= 0 ? detectionModel.model[detectionModel.currentIndex].about : ""
                        wrapMode: Text.Wrap
                        opacity: 0.7
                        Layout.preferredWidth: 360
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.M.Material.dividerColor }

        RowLayout {
            Layout.margins: 12
            Item { Layout.fillWidth: true }
            PointerButton { text: "Cancel"; flat: true; onClicked: settings.cancel() }
            PointerButton { objectName: "apply"; text: "Apply"; highlighted: true; onClicked: settings.apply() }
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

    // A setting's name, with what the setting does shown on hover
    component SettingLabel: RowLayout {
        id: label
        property alias text: name.text
        required property string tip
        spacing: 6
        Label { id: name }
        Label { text: "ⓘ"; opacity: 0.5 }
        HoverHandler { id: hover }
        // Its own, not the shared ToolTip.toolTip: rich text, whose lists indent, no wider than a paragraph.
        // Coloured like ToolTips.qml's.
        ToolTip {
            visible: hover.hovered
            text: label.tip
            width: Math.min(implicitWidth, 460)
            palette.toolTipBase: root.M.Material.tooltipColor
            palette.toolTipText: "white"
            Component.onCompleted: contentItem.textFormat = Text.RichText
        }
    }

    component SettingSwitch: PointerSwitch {
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

    // Only acceptable text is set, see `validator`
    component SettingField: CompactField {
        id: field
        required property string section
        required property string key
        Layout.preferredWidth: 160
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

    component SettingSpinBox: CompactSpinBox {
        id: field
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
            onTextEdited: settings.set_path(field.section, field.key, text)
        }
        CompactButton {
            text: "Browse"
            flat: true
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
        required property string tip
        spacing: 8

        function save() {
            if (red.acceptableInput && green.acceptableInput && blue.acceptableInput)
                settings.set(section, key, [Number(blue.text), Number(green.text), Number(red.text)])
        }

        SettingLabel { text: field.label; tip: field.tip; Layout.preferredWidth: 170 }
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
