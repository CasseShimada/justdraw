import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.0
import QtQuick.Window 2.15

ApplicationWindow {
    id: root

    property QtObject backend

    QtObject {
        id: uiMetrics

        readonly property int menuBarHeight: 22
        readonly property int menuBarHorizontalPadding: 2
        readonly property int menuBarVerticalPadding: 0
        readonly property int menuBarSpacing: 2
        readonly property int menuBarItemHeight: 20
        readonly property int menuBarItemVerticalPadding: 1
        readonly property int menuBarItemHorizontalPadding: 8
        readonly property int menuItemHeight: 20
        readonly property int menuItemVerticalPadding: 0
        readonly property int menuItemHorizontalPadding: 6
        readonly property int menuFontSize: 12
        readonly property int toolbarPadding: 8
        readonly property int toolbarButtonSize: 36
        readonly property int toolbarRadius: 10
        readonly property int toolbarSpacing: 6
        readonly property int toolbarBottomMargin: 24
        readonly property int toolbarImplicitHeight: 52
    }

    Component {
        id: compactMenuBarItemDelegate

        MenuBarItem {
            id: control
            visible: root.isTopMenuTitleVisible(control.text)
            implicitHeight: uiMetrics.menuBarItemHeight
            height: implicitHeight
            topPadding: uiMetrics.menuBarItemVerticalPadding
            bottomPadding: uiMetrics.menuBarItemVerticalPadding
            leftPadding: uiMetrics.menuBarItemHorizontalPadding
            rightPadding: uiMetrics.menuBarItemHorizontalPadding
            font.pixelSize: uiMetrics.menuFontSize
            palette.buttonText: "#f2f2f2"
            palette.windowText: "#f2f2f2"
            palette.highlightedText: "#f2f2f2"

            contentItem: Text {
                text: control.text
                color: control.enabled ? "#f2f2f2" : "#777777"
                font.pixelSize: uiMetrics.menuFontSize
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }

            background: Rectangle {
                color: control.highlighted ? "#2a2a2a" : "transparent"
                radius: 4
            }
        }
    }

    component CompactMenuBarItem : MenuBarItem {
        id: control
        visible: root.isTopMenuTitleVisible(control.text)
        implicitHeight: uiMetrics.menuBarItemHeight
        height: implicitHeight
        topPadding: uiMetrics.menuBarItemVerticalPadding
        bottomPadding: uiMetrics.menuBarItemVerticalPadding
        leftPadding: uiMetrics.menuBarItemHorizontalPadding
        rightPadding: uiMetrics.menuBarItemHorizontalPadding
        font.pixelSize: uiMetrics.menuFontSize
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        palette.highlightedText: "#f2f2f2"

        contentItem: Text {
            text: control.text
            color: control.enabled ? "#f2f2f2" : "#777777"
            font.pixelSize: uiMetrics.menuFontSize
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            color: control.highlighted ? "#2a2a2a" : "transparent"
            radius: 4
        }
    }

    component CompactSubMenuArrow : Text {
        color: parent && parent.enabled ? "#f2f2f2" : "#777777"
        font.pixelSize: 14
        font.bold: true
        text: "\u203a"
        width: 14
        height: uiMetrics.menuItemHeight
        anchors.right: parent ? parent.right : undefined
        anchors.rightMargin: uiMetrics.menuItemHorizontalPadding
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    Component {
        id: compactMenuItemDelegate

        CompactMenuItem {}
    }

    component CompactMenuItem : MenuItem {
        id: control
        property Menu presentedMenu: null
        readonly property bool hasSubMenu: !!(control.subMenu || control.presentedMenu)
        implicitHeight: uiMetrics.menuItemHeight
        height: implicitHeight
        padding: 0
        topPadding: uiMetrics.menuItemVerticalPadding
        bottomPadding: uiMetrics.menuItemVerticalPadding
        leftPadding: uiMetrics.menuItemHorizontalPadding
        rightPadding: hasSubMenu ? 22 : uiMetrics.menuItemHorizontalPadding
        font.pixelSize: uiMetrics.menuFontSize
        palette.text: "#f2f2f2"
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        palette.highlight: "#3a3a3a"
        palette.highlightedText: "#f2f2f2"

        contentItem: Text {
            text: control.text
            leftPadding: 0
            rightPadding: control.hasSubMenu ? 18 : 0
            color: control.enabled ? "#f2f2f2" : "#777777"
            font.pixelSize: uiMetrics.menuFontSize
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        arrow: CompactSubMenuArrow {
            visible: control.hasSubMenu
        }

        background: Rectangle {
            color: control.highlighted ? "#3a3a3a" : "transparent"
            radius: 4
        }
    }

    component CompactSubMenuItem : CompactMenuItem {
        id: control

        Timer {
            id: submenuCloseDelay
            interval: 140
            repeat: false
            onTriggered: {
                if (!control.presentedMenu || !control.presentedMenu.opened) {
                    return;
                }
                if (control.highlighted) {
                    return;
                }
                if (control.presentedMenu.pointerInside === true) {
                    return;
                }
                control.presentedMenu.close();
            }
        }

        function openPresentedMenu() {
            if (!presentedMenu) {
                return;
            }

            var p = mapToItem(Overlay.overlay, width - 1, 0);
            presentedMenu.x = p.x;
            presentedMenu.y = p.y;
            if (!presentedMenu.opened) {
                presentedMenu.open();
            }
        }

        onHighlightedChanged: {
            if (highlighted && menu && menu.opened) {
                submenuCloseDelay.stop();
                openPresentedMenu();
            } else {
                submenuCloseDelay.restart();
            }
        }

        onTriggered: {
            submenuCloseDelay.stop();
            openPresentedMenu();
        }

        Keys.onRightPressed: function(event) {
            submenuCloseDelay.stop();
            openPresentedMenu();
            event.accepted = true;
        }

        Keys.onEnterPressed: function(event) {
            submenuCloseDelay.stop();
            openPresentedMenu();
            event.accepted = true;
        }

        Keys.onReturnPressed: function(event) {
            submenuCloseDelay.stop();
            openPresentedMenu();
            event.accepted = true;
        }

        Connections {
            target: control.presentedMenu

            function onPointerInsideChanged() {
                if (control.presentedMenu.pointerInside === true) {
                    submenuCloseDelay.stop();
                } else if (!control.highlighted && control.presentedMenu.opened) {
                    submenuCloseDelay.restart();
                }
            }

            function onAboutToHide() {
                submenuCloseDelay.stop();
            }
        }
    }

    property string appMode: "photo_switching"

    property string photoSwitchingImagePath: ""
    property string colorPhotoImagePath: ""

    property string timerValue: "00:00"
    property string timerColor: "white"
    property int timerSeconds: 90
    property string playModeValue: "SEQ"
    property bool timerPaused: false
    property bool timerBlinkOn: true
    property string timerEndMode: "auto_next"
    property bool timerExpiredHold: false
    property bool prestartCountdownEnabled: false
    property bool prestartCountdownActive: false
    property int prestartCountdownValue: 0

    property bool stayOnTop: true
    property bool canRevealInExplorer: false
    property bool flipHorizontalEnabled: false
    property bool flipVerticalEnabled: false

    property int colorBlocksMinStripes: 1
    property int colorBlocksMaxStripes: 20
    property int colorBlocksStripeCount: 1
    property var colorBlocksPalette: []
    property real colorBlocksMinLuma: 0.22
    property real colorBlocksMaxLuma: 0.82
    property real colorBlocksMinSaturation: 0.35

    property bool colorPhotoCrystallizeEnabled: false

    property var recentImagePaths: []
    property bool applyingBackendWindowSize: false
    property int window_width: 840
    property int window_height: 1120

    property string colorThresholdEditKey: ""
    property string colorThresholdEditTitle: ""
    property string colorThresholdEditValue: ""
    property bool timerEditPausedByPopup: false
    property bool fileMenuAttached: false
    property bool modeMenuAttached: false
    property bool timerMenuAttached: false
    property bool colorSenseToolsMenuAttached: false

    Item {
        id: focusProxy
        visible: false
        width: 0
        height: 0
        focus: true
    }

    visible: true
    width: window_width
    height: window_height
    title: "Just Draw!"
    flags: stayOnTop
        ? (Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        : (Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)

    function isPhotoSwitchingMode() {
        return appMode === "photo_switching";
    }

    function isColorBlocksMode() {
        return appMode === "color_blocks";
    }

    function isColorPhotoMode() {
        return appMode === "color_photo";
    }

    function maxAllowedWindowWidth() {
        return Math.max(320, Screen.desktopAvailableWidth - 32);
    }

    function maxAllowedWindowHeight() {
        return Math.max(320, Screen.desktopAvailableHeight - 72);
    }

    function clampWindowWidth(value) {
        return Math.max(320, Math.min(value, maxAllowedWindowWidth()));
    }

    function clampWindowHeight(value) {
        return Math.max(320, Math.min(value, maxAllowedWindowHeight()));
    }

    function returnFocusToApp() {
        if (root.contentItem && root.contentItem.forceActiveFocus) {
            root.contentItem.forceActiveFocus();
            return;
        }
        focusProxy.forceActiveFocus();
    }

    function isTopMenuTitleVisible(title) {
        if (title === "Mode") {
            return true;
        }
        if (title === "File") {
            return isPhotoSwitchingMode() || isColorPhotoMode();
        }
        if (title === "Timer") {
            return isPhotoSwitchingMode();
        }
        if (title === "Color Sense Tools") {
            return isColorBlocksMode();
        }
        return true;
    }

    function debugLog(message) {
        if (backend && backend.debug_log) {
            backend.debug_log(String(message));
        }
    }

    function showActionToast(message) {
        actionToastText.text = message;
        if (actionToastAnimation.running) {
            actionToastAnimation.stop();
        }
        actionToastAnimation.start();
    }

    function normalizeRightAngle(value) {
        var angle = parseInt(value, 10) || 0;
        angle = angle % 360;
        if (angle < 0) {
            angle += 360;
        }
        return Math.round(angle / 90) * 90 % 360;
    }

    function timerEndModeText(mode) {
        if (mode === "auto_next") {
            return "Auto Next";
        }
        if (mode === "hold") {
            return "Stay On Current";
        }
        if (mode === "overtime") {
            return "Overtime Count Up";
        }
        return "Unknown";
    }

    function shouldBlinkTimerValue() {
        return isPhotoSwitchingMode() && (timerPaused || (timerEndMode === "hold" && timerExpiredHold));
    }

    function componentToHex(n) {
        var value = Math.max(0, Math.min(255, Math.round(n)));
        var hex = value.toString(16).toUpperCase();
        return hex.length < 2 ? ("0" + hex) : hex;
    }

    function rgbToHex(r, g, b) {
        return "#" + componentToHex(r) + componentToHex(g) + componentToHex(b);
    }

    function perceivedLuma(r, g, b) {
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0;
    }

    function hsvSaturation(r, g, b) {
        var maxValue = Math.max(r, g, b);
        var minValue = Math.min(r, g, b);
        if (maxValue <= 0) {
            return 0.0;
        }
        return (maxValue - minValue) / maxValue;
    }

    function formatThresholdValue(value) {
        return Number(Math.max(0.0, Math.min(1.0, value))).toFixed(2);
    }

    function generateColorBlock() {
        var minLuma = Math.max(0.0, Math.min(1.0, colorBlocksMinLuma));
        var maxLuma = Math.max(0.0, Math.min(1.0, colorBlocksMaxLuma));
        var minSaturation = Math.max(0.0, Math.min(1.0, colorBlocksMinSaturation));

        for (var i = 0; i < 120; i++) {
            var r = Math.floor(Math.random() * 256);
            var g = Math.floor(Math.random() * 256);
            var b = Math.floor(Math.random() * 256);
            var luma = perceivedLuma(r, g, b);
            var saturation = hsvSaturation(r, g, b);
            if (luma >= minLuma && luma <= maxLuma && saturation >= minSaturation) {
                return rgbToHex(r, g, b);
            }
        }

        return "#4DA6A6";
    }

    function normalizeColorBlocksStripeCount(value) {
        var parsed = parseInt(value, 10);
        if (!isFinite(parsed)) {
            parsed = colorBlocksMinStripes;
        }
        return Math.max(colorBlocksMinStripes, Math.min(colorBlocksMaxStripes, parsed));
    }

    function ensureColorBlocksPaletteLength(targetCount) {
        var normalizedCount = normalizeColorBlocksStripeCount(targetCount);
        var nextPalette = colorBlocksPalette.slice(0);
        while (nextPalette.length < normalizedCount) {
            nextPalette.push(generateColorBlock());
        }
        colorBlocksStripeCount = normalizedCount;
        colorBlocksPalette = nextPalette.slice(0, normalizedCount);
    }

    function persistColorBlocksSettings() {
        if (!backend) {
            return;
        }

        backend.set_color_blocks_settings(
            String(colorBlocksStripeCount),
            String(colorBlocksMinLuma),
            String(colorBlocksMaxLuma),
            String(colorBlocksMinSaturation)
        );
    }

    function adjustColorBlocksCount(step) {
        if (!isColorBlocksMode() || step === 0) {
            return;
        }

        ensureColorBlocksPaletteLength(colorBlocksStripeCount + step);
        persistColorBlocksSettings();
        showActionToast("Color count: " + colorBlocksStripeCount);
    }

    function refreshColorBlocksAction() {
        if (!isColorBlocksMode()) {
            return;
        }

        var nextPalette = [];
        for (var i = 0; i < colorBlocksStripeCount; i++) {
            nextPalette.push(generateColorBlock());
        }
        colorBlocksPalette = nextPalette;
        showActionToast("Colors refreshed");
    }

    function copyColorBlocksAction() {
        if (!backend || !isColorBlocksMode() || colorBlocksStripeCount <= 0) {
            showActionToast("Cannot copy colors");
            return;
        }

        var colors = colorBlocksPalette.slice(0, colorBlocksStripeCount);
        if (colors.length === 1) {
            var copiedPatch = backend.copy_color_patch(
                colors[0],
                String(Math.max(1, Math.round(colorBlocksCanvas.width))),
                String(Math.max(1, Math.round(colorBlocksCanvas.height)))
            );
            showActionToast(copiedPatch ? "Color copied" : "Cannot copy colors");
            return;
        }

        var copiedStripes = backend.copy_color_stripes(
            JSON.stringify(colors),
            String(Math.max(1, Math.round(colorBlocksCanvas.width))),
            String(Math.max(1, Math.round(colorBlocksCanvas.height)))
        );
        showActionToast(copiedStripes ? "Colors copied" : "Cannot copy colors");
    }

    function openColorThresholdEditPopup(key) {
        if (!isColorBlocksMode()) {
            return;
        }

        colorThresholdEditKey = key;
        if (key === "min_luma") {
            colorThresholdEditTitle = "Set Min Luma (0-1)";
            colorThresholdEditValue = formatThresholdValue(colorBlocksMinLuma);
        } else if (key === "max_luma") {
            colorThresholdEditTitle = "Set Max Luma (0-1)";
            colorThresholdEditValue = formatThresholdValue(colorBlocksMaxLuma);
        } else if (key === "min_saturation") {
            colorThresholdEditTitle = "Set Min Saturation (0-1)";
            colorThresholdEditValue = formatThresholdValue(colorBlocksMinSaturation);
        } else {
            return;
        }

        colorThresholdEditPopup.open();
    }

    function applyColorThresholdEditAction() {
        if (!backend || !isColorBlocksMode() || !colorThresholdEditInput.acceptableInput) {
            return;
        }

        var inputValue = Number(colorThresholdEditInput.text);
        if (!isFinite(inputValue)) {
            return;
        }

        inputValue = Math.max(0.0, Math.min(1.0, inputValue));

        var nextMinLuma = colorBlocksMinLuma;
        var nextMaxLuma = colorBlocksMaxLuma;
        var nextMinSaturation = colorBlocksMinSaturation;

        if (colorThresholdEditKey === "min_luma") {
            nextMinLuma = inputValue;
        } else if (colorThresholdEditKey === "max_luma") {
            nextMaxLuma = inputValue;
        } else if (colorThresholdEditKey === "min_saturation") {
            nextMinSaturation = inputValue;
        }

        if (nextMinLuma > nextMaxLuma) {
            showActionToast("Min luma must be <= max luma");
            return;
        }

        var changed = backend.set_color_blocks_settings(
            String(colorBlocksStripeCount),
            String(nextMinLuma),
            String(nextMaxLuma),
            String(nextMinSaturation)
        );
        if (changed) {
            colorBlocksMinLuma = nextMinLuma;
            colorBlocksMaxLuma = nextMaxLuma;
            colorBlocksMinSaturation = nextMinSaturation;
            showActionToast("Color thresholds updated");
        }

        colorThresholdEditPopup.close();
    }

    function activeImagePath() {
        if (isPhotoSwitchingMode()) {
            return photoSwitchingImagePath;
        }
        if (isColorPhotoMode()) {
            return colorPhotoImagePath;
        }
        return "";
    }

    function activeImageViewport() {
        if (isPhotoSwitchingMode()) {
            return photoSwitchingViewport;
        }
        if (isColorPhotoMode()) {
            return colorPhotoViewport;
        }
        return null;
    }

    function saveViewStateForViewport(viewport, imagePath) {
        if (!backend || !viewport || !imagePath) {
            return;
        }

        backend.save_image_view_state(
            String(viewport.imageScale),
            String(viewport.imageOffsetX),
            String(viewport.imageOffsetY),
            String(viewport.imageRotation)
        );
    }

    function savePhotoSwitchingViewStateNow() {
        saveViewStateForViewport(photoSwitchingViewport, photoSwitchingImagePath);
    }

    function saveColorPhotoViewStateNow() {
        saveViewStateForViewport(colorPhotoViewport, colorPhotoImagePath);
    }

    function saveCurrentImageViewStateNow() {
        if (isPhotoSwitchingMode()) {
            savePhotoSwitchingViewStateNow();
        } else if (isColorPhotoMode()) {
            saveColorPhotoViewStateNow();
        }
    }

    function saveGlobalFlipStateNow() {
        if (!backend) {
            return;
        }

        backend.save_global_flip_state(
            String(flipHorizontalEnabled),
            String(flipVerticalEnabled)
        );
    }

    function closeTopMenus() {
        fileMenu.close();
        recentPathsMenu.close();
        modeMenu.close();
        timerMenu.close();
        timerEndModeMenu.close();
        colorSenseToolsMenu.close();
    }

    function syncTopMenus() {
        return;
    }

    function closeTransientUi() {
        closeTopMenus();
        imageContextMenu.close();
        colorBlocksContextMenu.close();
        colorPhotoContextMenu.close();
        timerEditPopup.close();
        colorThresholdEditPopup.close();
    }

    function openContextMenu(menu, sourceItem, mouse) {
        if (!menu || !sourceItem) {
            debugLog("openContextMenu skipped: missing menu or sourceItem");
            return;
        }

        var p = sourceItem.mapToItem(Overlay.overlay, mouse.x, mouse.y);
        debugLog("openContextMenu " + menu + " local=(" + mouse.x + "," + mouse.y + ") overlay=(" + p.x + "," + p.y + ")");
        Qt.callLater(function() {
            if (!menu) {
                return;
            }
            menu.x = p.x;
            menu.y = p.y;
            menu.open();
        });
    }

    function refreshRecentImagePaths() {
        if (!backend) {
            recentImagePaths = [];
            return;
        }
        recentImagePaths = backend.get_recent_image_paths();
    }

    function setAppModeAction(mode) {
        if (!backend) {
            return;
        }

        saveCurrentImageViewStateNow();
        closeTopMenus();
        closeTransientUi();
        backend.set_app_mode(mode);
        Qt.callLater(function() {
            closeTopMenus();
            closeTransientUi();
            returnFocusToApp();
        });
    }

    function selectImageFolderAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        saveCurrentImageViewStateNow();
        if (backend.select_image_root_path()) {
            refreshRecentImagePaths();
            showActionToast("Image folder updated");
        }
    }

    function switchToRecentPath(path) {
        if (!backend || !path || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        saveCurrentImageViewStateNow();
        if (backend.set_image_root_path(path)) {
            refreshRecentImagePaths();
            showActionToast("Switched to " + path);
        } else {
            showActionToast("Cannot switch to selected path");
        }
    }

    function prevAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        saveCurrentImageViewStateNow();
        backend.prev();
    }

    function nextAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        saveCurrentImageViewStateNow();
        backend.next();
    }

    function prevInFolderAction() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        savePhotoSwitchingViewStateNow();
        backend.prev_in_folder();
    }

    function nextInFolderAction() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        savePhotoSwitchingViewStateNow();
        backend.next_in_folder();
    }

    function resetImageOrderAndPickRandomAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        saveCurrentImageViewStateNow();
        if (backend.reset_image_order_and_pick_random()) {
            showActionToast("Random image");
        } else {
            showActionToast("Cannot refresh image list");
        }
    }

    function togglePlayModeAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        var switchedTo = playModeValue === "SEQ" ? "Random mode enabled" : "Sequence mode enabled";
        backend.toggle_play_mode();
        showActionToast(switchedTo);
    }

    function toggleStayOnTopAction() {
        if (!backend) {
            return;
        }

        var enabling = !stayOnTop;
        backend.toggle_stay_on_top();
        showActionToast(enabling ? "Stay on top enabled" : "Stay on top disabled");
    }

    function toggleTimerPauseAction() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        var willResume = timerPaused;
        backend.pause();
        showActionToast(willResume ? "Timer resumed" : "Timer paused");
    }

    function resetTimerAction() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        backend.reset_timer();
        showActionToast("Timer reset");
    }

    function applyTimerValueAction(value) {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        backend.set_timer_value(value);
        showActionToast("Timer set to " + value + "s");
    }

    function setTimerEndModeAction(mode) {
        if (!backend || !isPhotoSwitchingMode() || timerEndMode === mode) {
            return;
        }

        backend.set_timer_end_mode(mode);
        showActionToast("Timer end mode: " + timerEndModeText(mode));
    }

    function togglePrestartCountdownAction() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        var willEnable = !prestartCountdownEnabled;
        backend.toggle_prestart_countdown_enabled();
        showActionToast(willEnable ? "3-second pre-start enabled" : "3-second pre-start disabled");
    }

    function openTimerEditPopup() {
        if (!backend || !isPhotoSwitchingMode()) {
            return;
        }

        timerEditPausedByPopup = false;
        if (!timerPaused) {
            backend.pause();
            timerEditPausedByPopup = true;
        }

        timerEditInput.text = String(timerSeconds);
        timerEditPopup.open();
    }

    function copyImageAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        var imagePath = activeImagePath();
        var viewport = activeImageViewport();
        if (!imagePath || !viewport) {
            showActionToast("Cannot copy current image");
            return;
        }

        viewport.grabToImage(function(result) {
            var tempPath = backend.allocate_temp_capture_path();
            if (result && tempPath && result.saveToFile(tempPath) && backend.copy_rendered_image(tempPath)) {
                showActionToast("Image copied");
            } else {
                showActionToast("Cannot copy current image");
            }
        });
    }

    function copyImagePathAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode()) || !activeImagePath()) {
            return;
        }

        if (backend.copy_image_path()) {
            showActionToast("Image path copied");
        }
    }

    function revealInExplorerAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        if (backend.reveal_current_image_in_explorer()) {
            showActionToast("Revealed in file explorer");
        } else {
            showActionToast("Cannot reveal current image");
        }
    }

    function resetCurrentImageStateAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        if (backend.reset_current_image_state()) {
            var viewport = activeImageViewport();
            if (viewport) {
                viewport.resetView();
            }
            showActionToast("Current image state reset");
        }
    }

    function resetCurrentPathImageStatesAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        if (backend.reset_current_path_image_states()) {
            showActionToast("Current path image states reset");
        } else {
            showActionToast("No image states to reset");
        }
    }

    function deletePathPlaybackStateAction() {
        if (!backend || !(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        if (backend.delete_path_playback_state()) {
            refreshRecentImagePaths();
            showActionToast("Path playback state deleted");
        } else {
            showActionToast("No path playback state deleted");
        }
    }

    function toggleHorizontalFlipAction() {
        if (!(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        flipHorizontalEnabled = !flipHorizontalEnabled;
        saveGlobalFlipStateNow();
        showActionToast(flipHorizontalEnabled ? "Horizontal flip enabled" : "Horizontal flip disabled");
    }

    function toggleVerticalFlipAction() {
        if (!(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return;
        }

        flipVerticalEnabled = !flipVerticalEnabled;
        saveGlobalFlipStateNow();
        showActionToast(flipVerticalEnabled ? "Vertical flip enabled" : "Vertical flip disabled");
    }

    function rotateCurrentImage(deltaDegrees) {
        if (!(isPhotoSwitchingMode() || isColorPhotoMode())) {
            return false;
        }

        var imagePath = activeImagePath();
        var viewport = activeImageViewport();
        if (!imagePath || !viewport) {
            return false;
        }

        viewport.imageRotation = normalizeRightAngle(viewport.imageRotation + deltaDegrees);
        viewport.applyImageGeometry();
        if (isPhotoSwitchingMode()) {
            persistPhotoSwitchingViewStateTimer.restart();
        } else if (isColorPhotoMode()) {
            persistColorPhotoViewStateTimer.restart();
        }
        return true;
    }

    function rotateLeftAction() {
        if (rotateCurrentImage(-90)) {
            showActionToast("Rotated left");
        }
    }

    function rotateRightAction() {
        if (rotateCurrentImage(90)) {
            showActionToast("Rotated right");
        }
    }

    function toggleColorPhotoCrystallizeAction() {
        if (!backend || !isColorPhotoMode()) {
            return;
        }

        backend.set_color_photo_crystallize_enabled(!colorPhotoCrystallizeEnabled);
        showActionToast(!colorPhotoCrystallizeEnabled ? "Crystallize enabled" : "Crystallize disabled");
    }

    menuBar: MenuBar {
        id: appMenuBar
        implicitHeight: uiMetrics.menuBarHeight
        height: implicitHeight
        topPadding: uiMetrics.menuBarVerticalPadding
        bottomPadding: uiMetrics.menuBarVerticalPadding
        leftPadding: uiMetrics.menuBarHorizontalPadding
        rightPadding: uiMetrics.menuBarHorizontalPadding
        spacing: uiMetrics.menuBarSpacing
        font.pixelSize: uiMetrics.menuFontSize
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        background: Rectangle { color: "#111111" }
        delegate: compactMenuBarItemDelegate

        Menu {
            id: fileMenu
            title: "File"
            popupType: Popup.Item
            implicitWidth: 220
            width: implicitWidth
            visible: isPhotoSwitchingMode() || isColorPhotoMode()
            delegate: compactMenuItemDelegate
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0
            font.pixelSize: uiMetrics.menuFontSize
            palette.text: "#f2f2f2"
            palette.buttonText: "#f2f2f2"
            palette.windowText: "#f2f2f2"
            palette.highlight: "#3a3a3a"
            palette.highlightedText: "#f2f2f2"
            background: Rectangle {
                color: "#202020"
                border.color: "#5a5a5a"
                border.width: 1
                radius: 6
            }
            onAboutToShow: debugLog("fileMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
            onAboutToHide: debugLog("fileMenu aboutToHide")

            CompactMenuItem {
                text: "Set Image Folder..."
                onTriggered: selectImageFolderAction()
            }

            CompactSubMenuItem {
                text: "Recent Paths"
                presentedMenu: recentPathsMenu

                Menu {
                    id: recentPathsMenu
                    title: "Recent Paths"
                    parent: Overlay.overlay
                    property bool pointerInside: submenuHover.hovered
                    popupType: Popup.Item
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    implicitWidth: 260
                    width: implicitWidth
                    delegate: compactMenuItemDelegate
                    padding: 0
                    topPadding: 0
                    bottomPadding: 0
                    leftPadding: 0
                    rightPadding: 0
                    font.pixelSize: uiMetrics.menuFontSize
                    palette.text: "#f2f2f2"
                    palette.buttonText: "#f2f2f2"
                    palette.windowText: "#f2f2f2"
                    palette.highlight: "#3a3a3a"
                    palette.highlightedText: "#f2f2f2"
                    background: Rectangle {
                        color: "#202020"
                        border.color: "#5a5a5a"
                        border.width: 1
                        radius: 6
                    }
                    HoverHandler {
                        id: submenuHover
                    }
                    onAboutToShow: {
                        debugLog("recentPathsMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")");
                        refreshRecentImagePaths();
                    }
                    onAboutToHide: debugLog("recentPathsMenu aboutToHide")

                    CompactMenuItem {
                        text: "(No recent paths)"
                        enabled: false
                        visible: recentImagePaths.length === 0
                    }

                    Instantiator {
                        model: recentImagePaths

                        delegate: CompactMenuItem {
                            text: modelData
                            onTriggered: switchToRecentPath(modelData)
                        }

                        onObjectAdded: function(index, object) {
                            recentPathsMenu.insertItem(index, object);
                        }

                        onObjectRemoved: function(index, object) {
                            recentPathsMenu.removeItem(object);
                        }
                    }
                }
            }

            MenuSeparator {}

            CompactMenuItem {
                text: "Delete Path Playback State..."
                onTriggered: deletePathPlaybackStateAction()
            }

            CompactMenuItem {
                text: "Refresh List Order + Random Image"
                onTriggered: resetImageOrderAndPickRandomAction()
            }

            CompactMenuItem {
                text: "Reset Current Path Image States"
                onTriggered: resetCurrentPathImageStatesAction()
            }
        }

        Menu {
            id: modeMenu
            title: "Mode"
            popupType: Popup.Item
            implicitWidth: 220
            width: implicitWidth
            delegate: compactMenuItemDelegate
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0
            font.pixelSize: uiMetrics.menuFontSize
            palette.text: "#f2f2f2"
            palette.buttonText: "#f2f2f2"
            palette.windowText: "#f2f2f2"
            palette.highlight: "#3a3a3a"
            palette.highlightedText: "#f2f2f2"
            background: Rectangle {
                color: "#202020"
                border.color: "#5a5a5a"
                border.width: 1
                radius: 6
            }
            onAboutToShow: debugLog("modeMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
            onAboutToHide: debugLog("modeMenu aboutToHide")

            CompactMenuItem {
                text: (isPhotoSwitchingMode() ? "✓ " : "") + "Photo Switching"
                onTriggered: setAppModeAction("photo_switching")
            }

            CompactMenuItem {
                text: (isColorBlocksMode() ? "✓ " : "") + "Color Blocks"
                onTriggered: setAppModeAction("color_blocks")
            }

            CompactMenuItem {
                text: (isColorPhotoMode() ? "✓ " : "") + "Color Photo"
                onTriggered: setAppModeAction("color_photo")
            }
        }

        Menu {
            id: timerMenu
            title: "Timer"
            popupType: Popup.Item
            implicitWidth: 220
            width: implicitWidth
            visible: isPhotoSwitchingMode()
            delegate: compactMenuItemDelegate
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0
            font.pixelSize: uiMetrics.menuFontSize
            palette.text: "#f2f2f2"
            palette.buttonText: "#f2f2f2"
            palette.windowText: "#f2f2f2"
            palette.highlight: "#3a3a3a"
            palette.highlightedText: "#f2f2f2"
            background: Rectangle {
                color: "#202020"
                border.color: "#5a5a5a"
                border.width: 1
                radius: 6
            }
            onAboutToShow: debugLog("timerMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
            onAboutToHide: debugLog("timerMenu aboutToHide")

            CompactMenuItem {
                text: timerPaused ? "Resume Timer" : "Pause Timer"
                onTriggered: toggleTimerPauseAction()
            }

            CompactMenuItem {
                text: "Set Timer..."
                onTriggered: openTimerEditPopup()
            }

            CompactMenuItem {
                text: "Reset Timer"
                onTriggered: resetTimerAction()
            }

            CompactMenuItem {
                text: (playModeValue === "RND" ? "✓ " : "") + "Random Play"
                onTriggered: togglePlayModeAction()
            }

            CompactMenuItem {
                text: (prestartCountdownEnabled ? "✓ " : "") + "3-second Pre-start Countdown"
                onTriggered: togglePrestartCountdownAction()
            }

            CompactSubMenuItem {
                text: "Timer End Mode"
                presentedMenu: timerEndModeMenu

                Menu {
                    id: timerEndModeMenu
                    title: "Timer End Mode"
                    parent: Overlay.overlay
                    property bool pointerInside: timerEndModeHover.hovered
                    popupType: Popup.Item
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    implicitWidth: 240
                    width: implicitWidth
                    delegate: compactMenuItemDelegate
                    padding: 0
                    topPadding: 0
                    bottomPadding: 0
                    leftPadding: 0
                    rightPadding: 0
                    font.pixelSize: uiMetrics.menuFontSize
                    palette.text: "#f2f2f2"
                    palette.buttonText: "#f2f2f2"
                    palette.windowText: "#f2f2f2"
                    palette.highlight: "#3a3a3a"
                    palette.highlightedText: "#f2f2f2"
                    background: Rectangle {
                        color: "#202020"
                        border.color: "#5a5a5a"
                        border.width: 1
                        radius: 6
                    }
                    HoverHandler {
                        id: timerEndModeHover
                    }
                    onAboutToShow: debugLog("timerEndModeMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
                    onAboutToHide: debugLog("timerEndModeMenu aboutToHide")

                    CompactMenuItem {
                        text: (timerEndMode === "auto_next" ? "✓ " : "") + "Auto Next Image"
                        onTriggered: setTimerEndModeAction("auto_next")
                    }

                    CompactMenuItem {
                        text: (timerEndMode === "hold" ? "✓ " : "") + "Stay On Current Image"
                        onTriggered: setTimerEndModeAction("hold")
                    }

                    CompactMenuItem {
                        text: (timerEndMode === "overtime" ? "✓ " : "") + "Overtime Count Up"
                        onTriggered: setTimerEndModeAction("overtime")
                    }
                }
            }
        }

        Menu {
            id: colorSenseToolsMenu
            title: "Color Sense Tools"
            popupType: Popup.Item
            implicitWidth: 220
            width: implicitWidth
            visible: isColorBlocksMode()
            delegate: compactMenuItemDelegate
            padding: 0
            topPadding: 0
            bottomPadding: 0
            leftPadding: 0
            rightPadding: 0
            font.pixelSize: uiMetrics.menuFontSize
            palette.text: "#f2f2f2"
            palette.buttonText: "#f2f2f2"
            palette.windowText: "#f2f2f2"
            palette.highlight: "#3a3a3a"
            palette.highlightedText: "#f2f2f2"
            background: Rectangle {
                color: "#202020"
                border.color: "#5a5a5a"
                border.width: 1
                radius: 6
            }
            onAboutToShow: debugLog("colorSenseToolsMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
            onAboutToHide: debugLog("colorSenseToolsMenu aboutToHide")

            CompactMenuItem {
                text: "Increase Colors"
                onTriggered: adjustColorBlocksCount(1)
            }

            CompactMenuItem {
                text: "Decrease Colors"
                onTriggered: adjustColorBlocksCount(-1)
            }

            CompactMenuItem {
                text: "Refresh Colors"
                onTriggered: refreshColorBlocksAction()
            }

            CompactMenuItem {
                text: "Copy Colors"
                onTriggered: copyColorBlocksAction()
            }

            MenuSeparator {}

            CompactMenuItem {
                text: "Set Min Luma..."
                onTriggered: openColorThresholdEditPopup("min_luma")
            }

            CompactMenuItem {
                text: "Set Max Luma..."
                onTriggered: openColorThresholdEditPopup("max_luma")
            }

            CompactMenuItem {
                text: "Set Min Saturation..."
                onTriggered: openColorThresholdEditPopup("min_saturation")
            }
        }
    }

    Menu {
        id: imageContextMenu
        parent: Overlay.overlay
        popupType: Popup.Item
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        implicitWidth: 220
        width: implicitWidth
        delegate: compactMenuItemDelegate
        padding: 0
        topPadding: 0
        bottomPadding: 0
        leftPadding: 0
        rightPadding: 0
        font.pixelSize: uiMetrics.menuFontSize
        palette.text: "#f2f2f2"
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        palette.highlight: "#3a3a3a"
        palette.highlightedText: "#f2f2f2"
        background: Rectangle {
            color: "#202020"
            border.color: "#5a5a5a"
            border.width: 1
            radius: 6
        }
        onAboutToShow: debugLog("imageContextMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
        onAboutToHide: debugLog("imageContextMenu aboutToHide")

        CompactMenuItem {
            text: timerPaused ? "Resume Timer" : "Pause Timer"
            onTriggered: toggleTimerPauseAction()
        }

        CompactMenuItem {
            text: "Reset Timer"
            onTriggered: resetTimerAction()
        }

        CompactMenuItem {
            text: (playModeValue === "RND" ? "✓ " : "") + "Random Play"
            onTriggered: togglePlayModeAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: "Set Image Folder..."
            onTriggered: selectImageFolderAction()
        }

        CompactMenuItem {
            text: "Random Image"
            onTriggered: resetImageOrderAndPickRandomAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: "Copy Image"
            onTriggered: copyImageAction()
        }

        CompactMenuItem {
            text: "Copy Image Path"
            onTriggered: copyImagePathAction()
        }

        CompactMenuItem {
            text: "Show In File Explorer"
            visible: canRevealInExplorer
            onTriggered: revealInExplorerAction()
        }

        CompactMenuItem {
            text: "Reset Current Image State"
            onTriggered: resetCurrentImageStateAction()
        }

        CompactMenuItem {
            text: "Reset Current Path Image States"
            onTriggered: resetCurrentPathImageStatesAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: (flipHorizontalEnabled ? "✓ " : "") + "Flip Horizontal"
            onTriggered: toggleHorizontalFlipAction()
        }

        CompactMenuItem {
            text: (flipVerticalEnabled ? "✓ " : "") + "Flip Vertical"
            onTriggered: toggleVerticalFlipAction()
        }

        CompactMenuItem {
            text: "Rotate -90"
            onTriggered: rotateLeftAction()
        }

        CompactMenuItem {
            text: "Rotate +90"
            onTriggered: rotateRightAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: (stayOnTop ? "✓ " : "") + "Stay On Top"
            onTriggered: toggleStayOnTopAction()
        }
    }

    Menu {
        id: colorBlocksContextMenu
        parent: Overlay.overlay
        popupType: Popup.Item
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        implicitWidth: 220
        width: implicitWidth
        delegate: compactMenuItemDelegate
        padding: 0
        topPadding: 0
        bottomPadding: 0
        leftPadding: 0
        rightPadding: 0
        font.pixelSize: uiMetrics.menuFontSize
        palette.text: "#f2f2f2"
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        palette.highlight: "#3a3a3a"
        palette.highlightedText: "#f2f2f2"
        background: Rectangle {
            color: "#202020"
            border.color: "#5a5a5a"
            border.width: 1
            radius: 6
        }
        onAboutToShow: debugLog("colorBlocksContextMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
        onAboutToHide: debugLog("colorBlocksContextMenu aboutToHide")

        CompactMenuItem {
            text: "Increase Colors"
            onTriggered: adjustColorBlocksCount(1)
        }

        CompactMenuItem {
            text: "Decrease Colors"
            onTriggered: adjustColorBlocksCount(-1)
        }

        CompactMenuItem {
            text: "Refresh Colors"
            onTriggered: refreshColorBlocksAction()
        }

        CompactMenuItem {
            text: "Copy Colors"
            onTriggered: copyColorBlocksAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: "Set Min Luma..."
            onTriggered: openColorThresholdEditPopup("min_luma")
        }

        CompactMenuItem {
            text: "Set Max Luma..."
            onTriggered: openColorThresholdEditPopup("max_luma")
        }

        CompactMenuItem {
            text: "Set Min Saturation..."
            onTriggered: openColorThresholdEditPopup("min_saturation")
        }

        MenuSeparator {}

        CompactMenuItem {
            text: (stayOnTop ? "✓ " : "") + "Stay On Top"
            onTriggered: toggleStayOnTopAction()
        }
    }

    Menu {
        id: colorPhotoContextMenu
        parent: Overlay.overlay
        popupType: Popup.Item
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        implicitWidth: 220
        width: implicitWidth
        delegate: compactMenuItemDelegate
        padding: 0
        topPadding: 0
        bottomPadding: 0
        leftPadding: 0
        rightPadding: 0
        font.pixelSize: uiMetrics.menuFontSize
        palette.text: "#f2f2f2"
        palette.buttonText: "#f2f2f2"
        palette.windowText: "#f2f2f2"
        palette.highlight: "#3a3a3a"
        palette.highlightedText: "#f2f2f2"
        background: Rectangle {
            color: "#202020"
            border.color: "#5a5a5a"
            border.width: 1
            radius: 6
        }
        onAboutToShow: debugLog("colorPhotoContextMenu aboutToShow at (" + x + "," + y + ") size=(" + width + "x" + height + ")")
        onAboutToHide: debugLog("colorPhotoContextMenu aboutToHide")

        CompactMenuItem {
            text: "Set Image Folder..."
            onTriggered: selectImageFolderAction()
        }

        CompactMenuItem {
            text: (playModeValue === "RND" ? "✓ " : "") + "Random Play"
            onTriggered: togglePlayModeAction()
        }

        CompactMenuItem {
            text: "Next Random Photo"
            onTriggered: resetImageOrderAndPickRandomAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: "Copy Image"
            onTriggered: copyImageAction()
        }

        CompactMenuItem {
            text: "Copy Image Path"
            onTriggered: copyImagePathAction()
        }

        CompactMenuItem {
            text: "Show In File Explorer"
            visible: canRevealInExplorer
            onTriggered: revealInExplorerAction()
        }

        CompactMenuItem {
            text: "Reset Current Image State"
            onTriggered: resetCurrentImageStateAction()
        }

        CompactMenuItem {
            text: "Reset Current Path Image States"
            onTriggered: resetCurrentPathImageStatesAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: (flipHorizontalEnabled ? "✓ " : "") + "Flip Horizontal"
            onTriggered: toggleHorizontalFlipAction()
        }

        CompactMenuItem {
            text: (flipVerticalEnabled ? "✓ " : "") + "Flip Vertical"
            onTriggered: toggleVerticalFlipAction()
        }

        CompactMenuItem {
            text: "Rotate -90"
            onTriggered: rotateLeftAction()
        }

        CompactMenuItem {
            text: "Rotate +90"
            onTriggered: rotateRightAction()
        }

        CompactMenuItem {
            text: (colorPhotoCrystallizeEnabled ? "✓ " : "") + "Crystallize"
            onTriggered: toggleColorPhotoCrystallizeAction()
        }

        MenuSeparator {}

        CompactMenuItem {
            text: (stayOnTop ? "✓ " : "") + "Stay On Top"
            onTriggered: toggleStayOnTopAction()
        }
    }

    Connections {
        target: backend

        function onSetappmode(mode) {
            if (mode !== "photo_switching" && mode !== "color_blocks" && mode !== "color_photo") {
                return;
            }

            appMode = mode;
            syncTopMenus();
            refreshRecentImagePaths();
        }

        function onSetcurtimer(val, col) {
            timerValue = val;
            timerColor = col;
        }

        function onSetcurimage(msg) {
            if (isPhotoSwitchingMode()) {
                photoSwitchingImagePath = msg;
            } else if (isColorPhotoMode()) {
                colorPhotoImagePath = msg;
            }
        }

        function onSetwindowsize(w, h) {
            var clampedW = clampWindowWidth(w);
            var clampedH = clampWindowHeight(h);
            applyingBackendWindowSize = true;
            window_width = clampedW;
            window_height = clampedH;
            width = clampedW;
            height = clampedH;
            applyingBackendWindowSize = false;
        }

        function onSetplaymode(mode) {
            playModeValue = mode;
        }

        function onSettimervalue(seconds) {
            timerSeconds = seconds;
        }

        function onSetstayontop(enabled) {
            stayOnTop = enabled;
        }

        function onSettimerendmode(mode) {
            timerEndMode = mode;
        }

        function onSettimerexpiredhold(enabled) {
            var wasExpiredHold = timerExpiredHold;
            timerExpiredHold = enabled;
            if (!wasExpiredHold && enabled && timerEndMode === "hold") {
                timerBlinkOn = true;
            }
        }

        function onSettimerpaused(enabled) {
            var wasPaused = timerPaused;
            timerPaused = enabled;
            if (wasPaused !== enabled) {
                timerBlinkOn = true;
            }
        }

        function onSetprestartenabled(enabled) {
            prestartCountdownEnabled = enabled;
        }

        function onSetprestartcountdown(seconds, active) {
            prestartCountdownValue = seconds;
            prestartCountdownActive = active;
        }

        function onSetcanrevealinexplorer(enabled) {
            canRevealInExplorer = enabled;
        }

        function onSetimageviewstate(scale, offset_x, offset_y, rotation, has_state) {
            if (isPhotoSwitchingMode()) {
                photoSwitchingViewport.pendingScale = scale;
                photoSwitchingViewport.pendingOffsetX = offset_x;
                photoSwitchingViewport.pendingOffsetY = offset_y;
                photoSwitchingViewport.pendingRotation = rotation;
                photoSwitchingViewport.pendingHasState = has_state;
                photoSwitchingViewport.applyPendingViewState();
            } else if (isColorPhotoMode()) {
                colorPhotoViewport.pendingScale = scale;
                colorPhotoViewport.pendingOffsetX = offset_x;
                colorPhotoViewport.pendingOffsetY = offset_y;
                colorPhotoViewport.pendingRotation = rotation;
                colorPhotoViewport.pendingHasState = has_state;
                colorPhotoViewport.applyPendingViewState();
            }
        }

        function onSetglobalflipstate(flip_horizontal, flip_vertical) {
            flipHorizontalEnabled = flip_horizontal;
            flipVerticalEnabled = flip_vertical;
        }

        function onSetcolorblocksettings(stripe_count, min_luma, max_luma, min_saturation) {
            colorBlocksStripeCount = normalizeColorBlocksStripeCount(stripe_count);
            colorBlocksMinLuma = Math.max(0.0, Math.min(1.0, min_luma));
            colorBlocksMaxLuma = Math.max(0.0, Math.min(1.0, max_luma));
            if (colorBlocksMinLuma > colorBlocksMaxLuma) {
                var temp = colorBlocksMinLuma;
                colorBlocksMinLuma = colorBlocksMaxLuma;
                colorBlocksMaxLuma = temp;
            }
            colorBlocksMinSaturation = Math.max(0.0, Math.min(1.0, min_saturation));
            ensureColorBlocksPaletteLength(colorBlocksStripeCount);
        }

        function onSetcolorphotocrystallizeenabled(enabled) {
            colorPhotoCrystallizeEnabled = enabled;
        }
    }

    Timer {
        id: timerClickDelay
        interval: 220
        repeat: false
        onTriggered: toggleTimerPauseAction()
    }

    Timer {
        id: persistWindowSizeTimer
        interval: 400
        repeat: false
        onTriggered: {
            if (!backend) {
                return;
            }

            var newW = Math.round(width);
            var newH = Math.round(height);
            window_width = newW;
            window_height = newH;
            backend.save_window_size(String(newW), String(newH));
        }
    }

    Timer {
        id: persistPhotoSwitchingViewStateTimer
        interval: 180
        repeat: false
        onTriggered: savePhotoSwitchingViewStateNow()
    }

    Timer {
        id: persistColorPhotoViewStateTimer
        interval: 180
        repeat: false
        onTriggered: saveColorPhotoViewStateNow()
    }

    Timer {
        id: pausedBlinkTimer
        interval: 1300
        repeat: true
        running: shouldBlinkTimerValue()
        onTriggered: timerBlinkOn = !timerBlinkOn
    }

    Shortcut {
        sequence: "Ctrl+C"
        context: Qt.WindowShortcut
        enabled: (isPhotoSwitchingMode() || isColorPhotoMode()) && activeImagePath() !== ""
        onActivated: copyImageAction()
    }

    Shortcut {
        sequence: "PgUp"
        context: Qt.WindowShortcut
        enabled: isPhotoSwitchingMode() || isColorPhotoMode()
        onActivated: prevAction()
    }

    Shortcut {
        sequence: "PgDown"
        context: Qt.WindowShortcut
        enabled: isPhotoSwitchingMode() || isColorPhotoMode()
        onActivated: nextAction()
    }

    Shortcut {
        sequence: "Space"
        context: Qt.WindowShortcut
        enabled: isPhotoSwitchingMode()
        onActivated: toggleTimerPauseAction()
    }

    onWidthChanged: {
        if (!applyingBackendWindowSize && visible && width > 0 && height > 0) {
            persistWindowSizeTimer.restart();
        }
    }

    onHeightChanged: {
        if (!applyingBackendWindowSize && visible && width > 0 && height > 0) {
            persistWindowSizeTimer.restart();
        }
    }

    onClosing: saveCurrentImageViewStateNow()

    Component.onCompleted: {
        refreshRecentImagePaths();
        syncTopMenus();
        Qt.callLater(function() {
            returnFocusToApp();
        });
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"

        Item {
            id: photoSwitchingPage
            anchors.fill: parent
            visible: isPhotoSwitchingMode()

            Item {
                id: photoSwitchingViewport
                anchors.fill: parent
                clip: true

                property real imageScale: 1.0
                property real minImageScale: 1.0
                property real maxImageScale: 8.0
                property real imageOffsetX: 0
                property real imageOffsetY: 0
                property real dragLastX: 0
                property real dragLastY: 0
                property int imageRotation: 0

                property real pendingScale: 1.0
                property real pendingOffsetX: 0
                property real pendingOffsetY: 0
                property int pendingRotation: 0
                property bool pendingHasState: false

                function fittedImageSize() {
                    if (width <= 0 || height <= 0) {
                        return { w: 0, h: 0 };
                    }
                    if (photoSwitchingImage.sourceSize.width <= 0 || photoSwitchingImage.sourceSize.height <= 0) {
                        return { w: width, h: height };
                    }

                    var fitScale = Math.min(width / photoSwitchingImage.sourceSize.width, height / photoSwitchingImage.sourceSize.height);
                    return {
                        w: photoSwitchingImage.sourceSize.width * fitScale,
                        h: photoSwitchingImage.sourceSize.height * fitScale
                    };
                }

                function applyImageGeometry() {
                    var fitted = fittedImageSize();
                    var targetWidth = fitted.w * imageScale;
                    var targetHeight = fitted.h * imageScale;

                    var maxOffsetX = Math.max(0, (targetWidth - width) / 2);
                    var maxOffsetY = Math.max(0, (targetHeight - height) / 2);
                    imageOffsetX = Math.max(-maxOffsetX, Math.min(maxOffsetX, imageOffsetX));
                    imageOffsetY = Math.max(-maxOffsetY, Math.min(maxOffsetY, imageOffsetY));

                    photoSwitchingImage.width = targetWidth;
                    photoSwitchingImage.height = targetHeight;
                    photoSwitchingImage.x = (width - targetWidth) / 2 + imageOffsetX;
                    photoSwitchingImage.y = (height - targetHeight) / 2 + imageOffsetY;
                }

                function resetView() {
                    imageScale = 1.0;
                    imageOffsetX = 0;
                    imageOffsetY = 0;
                    imageRotation = 0;
                    applyImageGeometry();
                }

                function applyPendingViewState() {
                    if (photoSwitchingImage.status !== Image.Ready) {
                        return;
                    }

                    if (pendingHasState) {
                        imageScale = Math.max(minImageScale, Math.min(maxImageScale, pendingScale));
                        imageOffsetX = pendingOffsetX;
                        imageOffsetY = pendingOffsetY;
                        imageRotation = normalizeRightAngle(pendingRotation);
                    } else {
                        imageScale = 1.0;
                        imageOffsetX = 0;
                        imageOffsetY = 0;
                        imageRotation = 0;
                    }

                    applyImageGeometry();
                }

                function zoomAt(mouseX, mouseY, deltaY) {
                    if (deltaY === 0) {
                        return;
                    }

                    var oldScale = imageScale;
                    var step = deltaY > 0 ? 1.12 : (1 / 1.12);
                    var newScale = Math.max(minImageScale, Math.min(maxImageScale, oldScale * step));
                    if (Math.abs(newScale - oldScale) < 0.00001) {
                        return;
                    }

                    var fitted = fittedImageSize();
                    var oldWidth = fitted.w * oldScale;
                    var oldHeight = fitted.h * oldScale;
                    var oldX = (width - oldWidth) / 2 + imageOffsetX;
                    var oldY = (height - oldHeight) / 2 + imageOffsetY;
                    var imageXRatio = oldWidth > 0 ? (mouseX - oldX) / oldWidth : 0.5;
                    var imageYRatio = oldHeight > 0 ? (mouseY - oldY) / oldHeight : 0.5;

                    imageScale = newScale;
                    var newWidth = fitted.w * imageScale;
                    var newHeight = fitted.h * imageScale;
                    imageOffsetX = mouseX - imageXRatio * newWidth - (width - newWidth) / 2;
                    imageOffsetY = mouseY - imageYRatio * newHeight - (height - newHeight) / 2;

                    applyImageGeometry();
                    persistPhotoSwitchingViewStateTimer.restart();
                }

                onWidthChanged: applyImageGeometry()
                onHeightChanged: applyImageGeometry()

                Image {
                    id: photoSwitchingImage
                    source: photoSwitchingImagePath
                    asynchronous: true
                    autoTransform: true
                    mipmap: true
                    smooth: true
                    fillMode: Image.PreserveAspectFit
                    transform: [
                        Scale {
                            origin.x: photoSwitchingImage.width / 2
                            origin.y: photoSwitchingImage.height / 2
                            xScale: flipHorizontalEnabled ? -1 : 1
                            yScale: flipVerticalEnabled ? -1 : 1
                        },
                        Rotation {
                            origin.x: photoSwitchingImage.width / 2
                            origin.y: photoSwitchingImage.height / 2
                            angle: photoSwitchingViewport.imageRotation
                        }
                    ]

                    onStatusChanged: {
                        if (status === Image.Ready) {
                            photoSwitchingViewport.applyPendingViewState();
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    hoverEnabled: true
                    cursorShape: ((pressedButtons & Qt.LeftButton) ? Qt.ClosedHandCursor : Qt.OpenHandCursor)

                    onPressed: function(mouse) {
                        photoSwitchingViewport.dragLastX = mouse.x;
                        photoSwitchingViewport.dragLastY = mouse.y;
                    }

                    onPositionChanged: function(mouse) {
                        if ((mouse.buttons & Qt.LeftButton) === 0) {
                            return;
                        }

                        photoSwitchingViewport.imageOffsetX += mouse.x - photoSwitchingViewport.dragLastX;
                        photoSwitchingViewport.imageOffsetY += mouse.y - photoSwitchingViewport.dragLastY;
                        photoSwitchingViewport.dragLastX = mouse.x;
                        photoSwitchingViewport.dragLastY = mouse.y;
                        photoSwitchingViewport.applyImageGeometry();
                        persistPhotoSwitchingViewStateTimer.restart();
                    }

                    onWheel: function(wheel) {
                        photoSwitchingViewport.zoomAt(wheel.x, wheel.y, wheel.angleDelta.y);
                        wheel.accepted = true;
                    }

                    onDoubleClicked: resetCurrentImageStateAction()
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton

                    onClicked: function(mouse) {
                        debugLog("photoSwitching right click at (" + mouse.x + "," + mouse.y + ")");
                        openContextMenu(imageContextMenu, this, mouse);
                        mouse.accepted = true;
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: prestartCountdownActive
                z: 20
                color: "#000000"
                opacity: 0.48

                Text {
                    anchors.centerIn: parent
                    text: String(prestartCountdownValue)
                    color: "white"
                    font.pixelSize: 180
                    font.bold: true
                }
            }

            Frame {
                id: timerFrame
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 12
                anchors.rightMargin: 12
                width: 130
                height: 52
                z: 30

                background: Rectangle {
                    color: "#101010"
                    opacity: 0.5
                    radius: 10
                }

                Text {
                    anchors.fill: parent
                    text: timerValue
                    font.pixelSize: 24
                    color: timerColor
                    opacity: shouldBlinkTimerValue() ? (timerBlinkOn ? 1.0 : 0.28) : 1.0
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    onClicked: timerClickDelay.restart()
                }
            }

            Frame {
                id: photoSwitchingToolbar
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: uiMetrics.toolbarBottomMargin
                z: 30
                padding: uiMetrics.toolbarPadding
                implicitWidth: photoSwitchingToolbarRow.implicitWidth + uiMetrics.toolbarPadding * 2
                implicitHeight: uiMetrics.toolbarImplicitHeight
                width: implicitWidth
                height: implicitHeight

                background: Rectangle {
                    color: "#101010"
                    radius: uiMetrics.toolbarRadius
                    opacity: 0.5
                }

                Row {
                    id: photoSwitchingToolbarRow
                    anchors.centerIn: parent
                    spacing: uiMetrics.toolbarSpacing

                    Button {
                        id: photoPrevButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/prev.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: photoPrevButton.down ? 1.0 : (photoPrevButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: prevAction()
                    }

                    Button {
                        id: photoPrevFolderButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/prev_in_folder.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: photoPrevFolderButton.down ? 1.0 : (photoPrevFolderButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: prevInFolderAction()
                    }

                    Button {
                        id: photoFlipHButton
                        width: 44
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Text {
                            text: "Flip H"
                            anchors.centerIn: parent
                            font.pixelSize: 12
                            color: photoFlipHButton.down ? "#ffffff" : (flipHorizontalEnabled ? "#f2f2f2" : "#cccccc")
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        onClicked: toggleHorizontalFlipAction()
                    }

                    Button {
                        id: photoFlipVButton
                        width: 44
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Text {
                            text: "Flip V"
                            anchors.centerIn: parent
                            font.pixelSize: 12
                            color: photoFlipVButton.down ? "#ffffff" : (flipVerticalEnabled ? "#f2f2f2" : "#cccccc")
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        onClicked: toggleVerticalFlipAction()
                    }

                    Button {
                        id: photoRotatePlusButton
                        width: 42
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Text {
                            text: "+90"
                            anchors.centerIn: parent
                            font.pixelSize: 12
                            color: photoRotatePlusButton.down ? "#ffffff" : "#cccccc"
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        onClicked: rotateRightAction()
                    }

                    Button {
                        id: photoRotateMinusButton
                        width: 42
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Text {
                            text: "-90"
                            anchors.centerIn: parent
                            font.pixelSize: 12
                            color: photoRotateMinusButton.down ? "#ffffff" : "#cccccc"
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        onClicked: rotateLeftAction()
                    }

                    Button {
                        id: photoNextFolderButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/next_in_folder.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: photoNextFolderButton.down ? 1.0 : (photoNextFolderButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: nextInFolderAction()
                    }

                    Button {
                        id: photoNextButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/next.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: photoNextButton.down ? 1.0 : (photoNextButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: nextAction()
                    }
                }
            }

        }

        Item {
            id: colorBlocksPage
            anchors.fill: parent
            visible: isColorBlocksMode()

            Rectangle {
                id: colorBlocksCanvas
                anchors.fill: parent
                color: "#000000"

                Repeater {
                    model: colorBlocksStripeCount

                    delegate: Rectangle {
                        property int leftEdge: Math.floor(index * colorBlocksCanvas.width / Math.max(1, colorBlocksStripeCount))
                        property int rightEdge: Math.floor((index + 1) * colorBlocksCanvas.width / Math.max(1, colorBlocksStripeCount))
                        x: leftEdge
                        y: 0
                        width: Math.max(1, rightEdge - leftEdge)
                        height: colorBlocksCanvas.height
                        color: index < colorBlocksPalette.length ? colorBlocksPalette[index] : "#808080"
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    hoverEnabled: true

                    onWheel: function(wheel) {
                        if ((wheel.modifiers & Qt.ControlModifier) !== 0) {
                            var step = wheel.angleDelta.y > 0 ? 1 : (wheel.angleDelta.y < 0 ? -1 : 0);
                            if (step !== 0) {
                                adjustColorBlocksCount(step);
                            }
                            wheel.accepted = true;
                            return;
                        }
                        wheel.accepted = false;
                    }

                    onClicked: function(mouse) {
                        debugLog("colorBlocks right click at (" + mouse.x + "," + mouse.y + ")");
                        openContextMenu(colorBlocksContextMenu, this, mouse);
                        mouse.accepted = true;
                    }
                }
            }

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: 12
                anchors.topMargin: 12
                radius: 8
                color: "#101010"
                opacity: 0.62
                width: colorBlocksCountLabel.implicitWidth + 20
                height: colorBlocksCountLabel.implicitHeight + 12

                Text {
                    id: colorBlocksCountLabel
                    anchors.centerIn: parent
                    text: "Colors: " + colorBlocksStripeCount
                    color: "white"
                    font.pixelSize: 13
                }
            }

        }

        Item {
            id: colorPhotoPage
            anchors.fill: parent
            visible: isColorPhotoMode()

            Item {
                id: colorPhotoViewport
                anchors.fill: parent
                clip: true

                property real imageScale: 1.0
                property real minImageScale: 1.0
                property real maxImageScale: 8.0
                property real imageOffsetX: 0
                property real imageOffsetY: 0
                property real dragLastX: 0
                property real dragLastY: 0
                property int imageRotation: 0

                property real pendingScale: 1.0
                property real pendingOffsetX: 0
                property real pendingOffsetY: 0
                property int pendingRotation: 0
                property bool pendingHasState: false

                function fittedImageSize() {
                    if (width <= 0 || height <= 0) {
                        return { w: 0, h: 0 };
                    }
                    if (colorPhotoImage.sourceSize.width <= 0 || colorPhotoImage.sourceSize.height <= 0) {
                        return { w: width, h: height };
                    }

                    var fitScale = Math.min(width / colorPhotoImage.sourceSize.width, height / colorPhotoImage.sourceSize.height);
                    return {
                        w: colorPhotoImage.sourceSize.width * fitScale,
                        h: colorPhotoImage.sourceSize.height * fitScale
                    };
                }

                function applyImageGeometry() {
                    var fitted = fittedImageSize();
                    var targetWidth = fitted.w * imageScale;
                    var targetHeight = fitted.h * imageScale;

                    var maxOffsetX = Math.max(0, (targetWidth - width) / 2);
                    var maxOffsetY = Math.max(0, (targetHeight - height) / 2);
                    imageOffsetX = Math.max(-maxOffsetX, Math.min(maxOffsetX, imageOffsetX));
                    imageOffsetY = Math.max(-maxOffsetY, Math.min(maxOffsetY, imageOffsetY));

                    colorPhotoImage.width = targetWidth;
                    colorPhotoImage.height = targetHeight;
                    colorPhotoImage.x = (width - targetWidth) / 2 + imageOffsetX;
                    colorPhotoImage.y = (height - targetHeight) / 2 + imageOffsetY;
                }

                function resetView() {
                    imageScale = 1.0;
                    imageOffsetX = 0;
                    imageOffsetY = 0;
                    imageRotation = 0;
                    applyImageGeometry();
                }

                function applyPendingViewState() {
                    if (colorPhotoImage.status !== Image.Ready) {
                        return;
                    }

                    if (pendingHasState) {
                        imageScale = Math.max(minImageScale, Math.min(maxImageScale, pendingScale));
                        imageOffsetX = pendingOffsetX;
                        imageOffsetY = pendingOffsetY;
                        imageRotation = normalizeRightAngle(pendingRotation);
                    } else {
                        imageScale = 1.0;
                        imageOffsetX = 0;
                        imageOffsetY = 0;
                        imageRotation = 0;
                    }

                    applyImageGeometry();
                }

                function zoomAt(mouseX, mouseY, deltaY) {
                    if (deltaY === 0) {
                        return;
                    }

                    var oldScale = imageScale;
                    var step = deltaY > 0 ? 1.12 : (1 / 1.12);
                    var newScale = Math.max(minImageScale, Math.min(maxImageScale, oldScale * step));
                    if (Math.abs(newScale - oldScale) < 0.00001) {
                        return;
                    }

                    var fitted = fittedImageSize();
                    var oldWidth = fitted.w * oldScale;
                    var oldHeight = fitted.h * oldScale;
                    var oldX = (width - oldWidth) / 2 + imageOffsetX;
                    var oldY = (height - oldHeight) / 2 + imageOffsetY;
                    var imageXRatio = oldWidth > 0 ? (mouseX - oldX) / oldWidth : 0.5;
                    var imageYRatio = oldHeight > 0 ? (mouseY - oldY) / oldHeight : 0.5;

                    imageScale = newScale;
                    var newWidth = fitted.w * imageScale;
                    var newHeight = fitted.h * imageScale;
                    imageOffsetX = mouseX - imageXRatio * newWidth - (width - newWidth) / 2;
                    imageOffsetY = mouseY - imageYRatio * newHeight - (height - newHeight) / 2;

                    applyImageGeometry();
                    persistColorPhotoViewStateTimer.restart();
                }

                onWidthChanged: applyImageGeometry()
                onHeightChanged: applyImageGeometry()

                Image {
                    id: colorPhotoSourceMeta
                    visible: false
                    source: colorPhotoImagePath
                    asynchronous: true
                    autoTransform: true
                }

                Image {
                    id: colorPhotoImage
                    source: colorPhotoImagePath
                    asynchronous: true
                    autoTransform: true
                    mipmap: true
                    smooth: !colorPhotoCrystallizeEnabled
                    sourceSize.width: (colorPhotoCrystallizeEnabled
                        && colorPhotoSourceMeta.status === Image.Ready
                        && colorPhotoSourceMeta.sourceSize.width > 0)
                        ? Math.max(8, Math.round(colorPhotoSourceMeta.sourceSize.width / 24))
                        : 0
                    sourceSize.height: (colorPhotoCrystallizeEnabled
                        && colorPhotoSourceMeta.status === Image.Ready
                        && colorPhotoSourceMeta.sourceSize.height > 0)
                        ? Math.max(8, Math.round(colorPhotoSourceMeta.sourceSize.height / 24))
                        : 0
                    fillMode: Image.PreserveAspectFit
                    transform: [
                        Scale {
                            origin.x: colorPhotoImage.width / 2
                            origin.y: colorPhotoImage.height / 2
                            xScale: flipHorizontalEnabled ? -1 : 1
                            yScale: flipVerticalEnabled ? -1 : 1
                        },
                        Rotation {
                            origin.x: colorPhotoImage.width / 2
                            origin.y: colorPhotoImage.height / 2
                            angle: colorPhotoViewport.imageRotation
                        }
                    ]

                    onStatusChanged: {
                        if (status === Image.Ready) {
                            colorPhotoViewport.applyPendingViewState();
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton
                    hoverEnabled: true
                    cursorShape: ((pressedButtons & Qt.LeftButton) ? Qt.ClosedHandCursor : Qt.OpenHandCursor)

                    onPressed: function(mouse) {
                        colorPhotoViewport.dragLastX = mouse.x;
                        colorPhotoViewport.dragLastY = mouse.y;
                    }

                    onPositionChanged: function(mouse) {
                        if ((mouse.buttons & Qt.LeftButton) === 0) {
                            return;
                        }

                        colorPhotoViewport.imageOffsetX += mouse.x - colorPhotoViewport.dragLastX;
                        colorPhotoViewport.imageOffsetY += mouse.y - colorPhotoViewport.dragLastY;
                        colorPhotoViewport.dragLastX = mouse.x;
                        colorPhotoViewport.dragLastY = mouse.y;
                        colorPhotoViewport.applyImageGeometry();
                        persistColorPhotoViewStateTimer.restart();
                    }

                    onWheel: function(wheel) {
                        colorPhotoViewport.zoomAt(wheel.x, wheel.y, wheel.angleDelta.y);
                        wheel.accepted = true;
                    }

                    onDoubleClicked: resetCurrentImageStateAction()
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton

                    onClicked: function(mouse) {
                        debugLog("colorPhoto right click at (" + mouse.x + "," + mouse.y + ")");
                        openContextMenu(colorPhotoContextMenu, this, mouse);
                        mouse.accepted = true;
                    }
                }
            }

            Frame {
                id: colorPhotoToolbar
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: uiMetrics.toolbarBottomMargin
                z: 30
                padding: uiMetrics.toolbarPadding
                implicitWidth: colorPhotoToolbarRow.implicitWidth + uiMetrics.toolbarPadding * 2
                implicitHeight: uiMetrics.toolbarImplicitHeight
                width: implicitWidth
                height: implicitHeight

                background: Rectangle {
                    color: "#101010"
                    radius: uiMetrics.toolbarRadius
                    opacity: 0.5
                }

                Row {
                    id: colorPhotoToolbarRow
                    anchors.centerIn: parent
                    spacing: uiMetrics.toolbarSpacing

                    Button {
                        id: colorPhotoPrevButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/prev.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: colorPhotoPrevButton.down ? 1.0 : (colorPhotoPrevButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: prevAction()
                    }

                    Button {
                        id: colorPhotoNextButton
                        width: uiMetrics.toolbarButtonSize
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Item {
                            Image {
                                anchors.centerIn: parent
                                width: 24
                                height: 24
                                source: "./images/next.png"
                                fillMode: Image.PreserveAspectFit
                                opacity: colorPhotoNextButton.down ? 1.0 : (colorPhotoNextButton.hovered ? 0.85 : 0.62)
                            }
                        }
                        onClicked: nextAction()
                    }

                    Button {
                        id: colorPhotoCrystalButton
                        width: 68
                        height: uiMetrics.toolbarButtonSize
                        background: Rectangle {
                            color: "transparent"
                            radius: 6
                        }
                        contentItem: Text {
                            text: colorPhotoCrystallizeEnabled ? "Crystal On" : "Crystal"
                            anchors.centerIn: parent
                            font.pixelSize: 12
                            color: colorPhotoCrystalButton.down ? "#ffffff" : (colorPhotoCrystallizeEnabled ? "#f2f2f2" : "#cccccc")
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        onClicked: toggleColorPhotoCrystallizeAction()
                    }
                }
            }

        }

        Popup {
            id: timerEditPopup
            parent: Overlay.overlay
            modal: true
            focus: true
            width: 240
            height: 136
            x: root.width - width - 12
            y: uiMetrics.menuBarHeight + 8
            padding: 0
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                opacity: 0.92
                color: "#101010"
                radius: 10
                border.color: "#505050"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                Label {
                    text: "Set seconds"
                    color: "white"
                    Layout.fillWidth: true
                }

                TextField {
                    id: timerEditInput
                    text: String(timerSeconds)
                    placeholderText: "seconds"
                    selectByMouse: true
                    Layout.fillWidth: true
                    validator: IntValidator {
                        bottom: 1
                        top: 3600
                    }

                    onAccepted: {
                        if (acceptableInput && text.length > 0) {
                            applyTimerValueAction(text);
                            timerEditPopup.close();
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        text: "Cancel"
                        onClicked: timerEditPopup.close()
                    }

                    Button {
                        text: "Apply"
                        onClicked: {
                            if (timerEditInput.acceptableInput && timerEditInput.text.length > 0) {
                                applyTimerValueAction(timerEditInput.text);
                                timerEditPopup.close();
                            }
                        }
                    }
                }
            }

            onOpened: {
                timerEditInput.forceActiveFocus();
                timerEditInput.selectAll();
            }

            onClosed: {
                if (timerEditPausedByPopup && backend) {
                    backend.pause();
                }
                timerEditPausedByPopup = false;
            }
        }

        Popup {
            id: colorThresholdEditPopup
            parent: Overlay.overlay
            modal: true
            focus: true
            width: 260
            height: 142
            x: root.width - width - 12
            y: uiMetrics.menuBarHeight + 8
            padding: 0
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                opacity: 0.92
                color: "#101010"
                radius: 10
                border.color: "#505050"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                Label {
                    text: colorThresholdEditTitle
                    color: "white"
                    Layout.fillWidth: true
                }

                TextField {
                    id: colorThresholdEditInput
                    text: colorThresholdEditValue
                    placeholderText: "0.00 - 1.00"
                    selectByMouse: true
                    Layout.fillWidth: true
                    validator: DoubleValidator {
                        bottom: 0.0
                        top: 1.0
                        decimals: 3
                    }
                    onAccepted: applyColorThresholdEditAction()
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Item {
                        Layout.fillWidth: true
                    }

                    Button {
                        text: "Cancel"
                        onClicked: colorThresholdEditPopup.close()
                    }

                    Button {
                        text: "Apply"
                        onClicked: applyColorThresholdEditAction()
                    }
                }
            }

            onOpened: {
                colorThresholdEditInput.forceActiveFocus();
                colorThresholdEditInput.selectAll();
            }
        }

        Rectangle {
            id: actionToast
            visible: false
            opacity: 0
            z: 100
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            radius: 8
            color: "#101010"
            width: actionToastText.implicitWidth + 28
            height: actionToastText.implicitHeight + 18

            Text {
                id: actionToastText
                anchors.centerIn: parent
                text: ""
                color: "white"
                font.pixelSize: 14
            }
        }

        SequentialAnimation {
            id: actionToastAnimation
            running: false

            ScriptAction {
                script: {
                    actionToast.visible = true;
                    actionToast.opacity = 0;
                }
            }

            NumberAnimation {
                target: actionToast
                property: "opacity"
                to: 0.74
                duration: 140
                easing.type: Easing.OutQuad
            }

            PauseAnimation {
                duration: 920
            }

            NumberAnimation {
                target: actionToast
                property: "opacity"
                to: 0
                duration: 220
                easing.type: Easing.InQuad
            }

            ScriptAction {
                script: actionToast.visible = false
            }
        }
    }
}
