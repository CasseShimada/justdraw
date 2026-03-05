import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.0
import QtQuick.Window 2.15

ApplicationWindow {
	property string curImagePath: ""
	property bool curImgMirror: false
	property bool curImgFlipVertical: false
	property int curImgRotation: 0

	property string timerValue: "00:00"
	property string timerColor: "white"
	property int timerSeconds: 90
	property bool timerPaused: false
	property bool timerBlinkOn: true
	property bool timerEditPausedByPopup: false
	property bool timerEditApplied: false
	property string playModeValue: "SEQ"
	property bool stayOnTop: true
	property string timerEndMode: "auto_next"
	property bool timerExpiredHold: false
	property bool canRevealInExplorer: false
	property bool prestartCountdownEnabled: false
	property bool prestartCountdownActive: false
	property int prestartCountdownValue: 0
	property bool applyingBackendWindowSize: false
	property var recentImagePaths: []

	property QtObject backend

	property int window_width: 840
	property int window_height: 1120

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

	function showActionToast(message) {
		actionToastText.text = message;
		if (actionToastAnimation.running) {
			actionToastAnimation.stop();
		}
		actionToastAnimation.start();
	}

	function formatClock(totalSeconds) {
		var seconds = Math.max(0, parseInt(totalSeconds, 10) || 0);
		var mm = Math.floor(seconds / 60);
		var ss = seconds % 60;
		return (mm < 10 ? "0" : "") + mm + ":" + (ss < 10 ? "0" : "") + ss;
	}

	function normalizeRightAngle(value) {
		var angle = parseInt(value, 10) || 0;
		angle = angle % 360;
		if (angle < 0) {
			angle += 360;
		}
		return Math.round(angle / 90) * 90 % 360;
	}

	function saveCurrentImageViewStateNow() {
		if (!backend || !curImagePath) {
			return;
		}

		backend.save_image_view_state(
			String(imageViewport.imageScale),
			String(imageViewport.imageOffsetX),
			String(imageViewport.imageOffsetY),
			String(curImgRotation)
		);
	}

	function saveGlobalFlipStateNow() {
		if (!backend) {
			return;
		}

		backend.save_global_flip_state(
			String(curImgMirror),
			String(curImgFlipVertical)
		);
	}

	function selectImageFolderAction() {
		if (!backend) {
			return;
		}

		saveCurrentImageViewStateNow();
		if (backend.select_image_root_path()) {
			refreshRecentImagePaths();
			showActionToast("Image folder updated");
		}
	}

	function toggleTimerPauseAction() {
		var willResume = timerPaused;
		backend.pause();
		showActionToast(willResume ? "Timer resumed" : "Timer paused");
	}

	function prevAction() {
		saveCurrentImageViewStateNow();
		backend.prev();
		showActionToast("Previous image");
	}

	function prevInFolderAction() {
		saveCurrentImageViewStateNow();
		backend.prev_in_folder();
		showActionToast("Previous image in folder");
	}

	function nextInFolderAction() {
		saveCurrentImageViewStateNow();
		backend.next_in_folder();
		showActionToast("Next image in folder");
	}

	function nextAction() {
		saveCurrentImageViewStateNow();
		backend.next();
		showActionToast("Next image");
	}

	function resetTimerAction() {
		backend.reset_timer();
		showActionToast("Timer reset");
	}

	function resetImageOrderAndPickRandomAction() {
		saveCurrentImageViewStateNow();
		if (backend.reset_image_order_and_pick_random()) {
			showActionToast("Image list refreshed, jumped to random image");
		} else {
			showActionToast("Cannot refresh image list");
		}
	}

	function resetCurrentPathImageStatesAction() {
		if (backend.reset_current_path_image_states()) {
			showActionToast("Current path image states reset");
		} else {
			showActionToast("No image states to reset");
		}
	}

	function resetCurrentImageStateAction() {
		if (!curImagePath) {
			showActionToast("No image loaded");
			return;
		}

		// Reset current runtime view immediately, then synchronize persistence.
		curImgRotation = 0;
		imageViewport.resetView();
		backend.reset_current_image_state();
		persistImageViewStateTimer.restart();
		showActionToast("Current image state reset");
	}

	function togglePlayModeAction() {
		var switchedTo = (playModeValue === "SEQ") ? "Random mode" : "Sequence mode";
		backend.toggle_play_mode();
		showActionToast(switchedTo + " enabled");
	}

	function toggleStayOnTopAction() {
		var state = stayOnTop ? "disabled" : "enabled";
		backend.toggle_stay_on_top();
		showActionToast("Stay on top " + state);
	}

	function copyImageAction() {
		if (!backend || !curImagePath) {
			showActionToast("Cannot copy current image");
			return;
		}

		imageViewport.grabToImage(function(result) {
			var tempPath = backend.allocate_temp_capture_path();
			if (result && tempPath && result.saveToFile(tempPath) && backend.copy_rendered_image(tempPath)) {
				showActionToast("Image copied successfully");
			} else {
				showActionToast("Cannot copy current image");
			}
		});
	}

	function copyImagePathAction() {
		if (backend.copy_image_path()) {
			showActionToast("Image path copied");
		}
	}

	function revealInExplorerAction() {
		if (backend.reveal_current_image_in_explorer()) {
			showActionToast("Revealed in file explorer");
		} else {
			showActionToast("Cannot reveal current image");
		}
	}

	function flipHorizontalAction() {
		curImgMirror = !curImgMirror;
		saveGlobalFlipStateNow();
		showActionToast(curImgMirror ? "Horizontal flip enabled" : "Horizontal flip disabled");
	}

	function flipVerticalAction() {
		curImgFlipVertical = !curImgFlipVertical;
		saveGlobalFlipStateNow();
		showActionToast(curImgFlipVertical ? "Vertical flip enabled" : "Vertical flip disabled");
	}

	function rotateClockwiseAction() {
		curImgRotation = normalizeRightAngle(curImgRotation + 90);
		persistImageViewStateTimer.restart();
		showActionToast("Rotated 90 degrees clockwise");
	}

	function rotateCounterClockwiseAction() {
		curImgRotation = normalizeRightAngle(curImgRotation - 90);
		persistImageViewStateTimer.restart();
		showActionToast("Rotated 90 degrees counterclockwise");
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

	function setTimerEndModeAction(mode) {
		if (!backend || timerEndMode === mode) {
			return;
		}

		backend.set_timer_end_mode(mode);
		showActionToast("Timer end mode: " + timerEndModeText(mode));
	}

	function deletePathPlaybackStateAction() {
		if (backend.delete_path_playback_state()) {
			refreshRecentImagePaths();
			showActionToast("Path playback state deleted");
		} else {
			showActionToast("No path playback state deleted");
		}
	}

	function refreshRecentImagePaths() {
		if (!backend) {
			recentImagePaths = [];
			return;
		}

		recentImagePaths = backend.get_recent_image_paths();
	}

	function switchToRecentPath(path) {
		if (!path || !backend) {
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

	function applyTimerValueAction(value) {
		backend.set_timer_value(value);
		showActionToast("Timer set to " + value + "s");
	}

	function togglePrestartCountdownAction() {
		var willEnable = !prestartCountdownEnabled;
		backend.toggle_prestart_countdown_enabled();
		showActionToast(willEnable ? "3-second pre-start countdown enabled" : "3-second pre-start countdown disabled");
	}

	function openTimerEditPopup() {
		timerEditApplied = false;
		timerEditPausedByPopup = false;
		if (!timerPaused) {
			backend.pause();
			timerEditPausedByPopup = true;
		}
		timerEditInput.text = String(timerSeconds);
		timerEditPopup.open();
	}

	function shouldBlinkTimerValue() {
		return timerPaused || (timerEndMode === "hold" && timerExpiredHold);
	}

	visible: true
	width: window_width
	height: window_height
	title: "Just Draw!"
	flags: stayOnTop
		? (Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
		: (Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)

	menuBar: MenuBar {
		id: appMenuBar
		implicitHeight: 22
		topPadding: 0
		bottomPadding: 0
		leftPadding: 2
		rightPadding: 2
		spacing: 2

		delegate: MenuBarItem {
			height: 20
			implicitHeight: 20
			topPadding: 1
			bottomPadding: 1
			leftPadding: 8
			rightPadding: 8
		}

		Menu {
			title: "File"
			delegate: MenuItem {
				implicitHeight: 20
				topPadding: 0
				bottomPadding: 0
				leftPadding: 6
				rightPadding: 6
				font.pixelSize: 12
			}

				MenuItem {
					height: 20
					text: "Set Image Folder..."
					onTriggered: selectImageFolderAction()
				}

			Menu {
				id: recentPathsMenu
				title: "Recent Paths"
				delegate: MenuItem {
					implicitHeight: 20
					topPadding: 0
					bottomPadding: 0
					leftPadding: 6
					rightPadding: 6
					font.pixelSize: 12
				}
				onAboutToShow: refreshRecentImagePaths()

					MenuItem {
						height: 20
						enabled: false
						visible: recentImagePaths.length === 0
						text: "(No recent paths)"
					}

				Instantiator {
					model: recentImagePaths

						delegate: MenuItem {
							height: 20
							text: modelData
							onTriggered: switchToRecentPath(modelData)
						}

					onObjectAdded: function(index, object) {
						recentPathsMenu.insertItem(index, object);
					}

					onObjectRemoved: function(index, object) {
						recentPathsMenu.removeItem(object);
						object.destroy();
					}
				}
			}

				MenuItem {
					height: 20
					text: "Delete Path Playback State..."
					onTriggered: deletePathPlaybackStateAction()
				}

				MenuItem {
					height: 20
					text: "Refresh List Order + Random Image"
					onTriggered: resetImageOrderAndPickRandomAction()
				}

				MenuItem {
					height: 20
					text: "Reset Current Path Image States"
					onTriggered: resetCurrentPathImageStatesAction()
				}
		}

			Menu {
				title: "Timer"
			delegate: MenuItem {
				implicitHeight: 20
				topPadding: 0
				bottomPadding: 0
				leftPadding: 6
				rightPadding: 6
				font.pixelSize: 12
			}

				MenuItem {
					height: 20
					text: "Set Timer..."
					onTriggered: openTimerEditPopup()
				}

				MenuItem {
					id: prestartCountdownMenuItem
					height: 20
					text: ""
					contentItem: RowLayout {
						anchors.fill: parent
						anchors.leftMargin: 6
						anchors.rightMargin: 6
						spacing: 6

						Text {
							text: "3-second Pre-start Countdown"
							color: prestartCountdownMenuItem.enabled
								? (prestartCountdownMenuItem.highlighted
									? prestartCountdownMenuItem.palette.highlightedText
									: prestartCountdownMenuItem.palette.text)
								: prestartCountdownMenuItem.palette.mid
							font.pixelSize: 12
							elide: Text.ElideRight
							verticalAlignment: Text.AlignVCenter
							Layout.fillWidth: true
						}

						Text {
							visible: prestartCountdownEnabled
							text: "✓"
							color: prestartCountdownMenuItem.highlighted
								? prestartCountdownMenuItem.palette.highlightedText
								: prestartCountdownMenuItem.palette.text
							font.pixelSize: 10
							verticalAlignment: Text.AlignVCenter
						}
					}
					onTriggered: togglePrestartCountdownAction()
				}

			Menu {
				title: "Timer End Mode"
				delegate: MenuItem {
					implicitHeight: 20
					topPadding: 0
					bottomPadding: 0
					leftPadding: 6
					rightPadding: 6
					font.pixelSize: 12
				}

					MenuItem {
						height: 20
						text: (timerEndMode === "auto_next" ? "✓ " : "") + "Auto Next Image"
						onTriggered: setTimerEndModeAction("auto_next")
					}

					MenuItem {
						height: 20
						text: (timerEndMode === "hold" ? "✓ " : "") + "Stay On Current Image"
						onTriggered: setTimerEndModeAction("hold")
					}

					MenuItem {
						height: 20
						text: (timerEndMode === "overtime" ? "✓ " : "") + "Overtime Count Up"
						onTriggered: setTimerEndModeAction("overtime")
					}
			}
		}
	}

	Connections {
		target: backend

		function onSetcurtimer(val, col) {
			timerValue = val;
			timerColor = col;
		}

			function onSetcurimage(msg) {
				curImagePath = msg;
				curImgRotation = 0;
				imageViewport.resetView();
			}

		function onSetglobalflipstate(flip_horizontal, flip_vertical) {
			curImgMirror = flip_horizontal;
			curImgFlipVertical = flip_vertical;
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

				function onSetimageviewstate(scale, offset_x, offset_y, rotation, has_state) {
					imageViewport.pendingScale = scale;
					imageViewport.pendingOffsetX = offset_x;
					imageViewport.pendingOffsetY = offset_y;
					imageViewport.pendingRotation = rotation;
					imageViewport.pendingHasState = has_state;
					imageViewport.applyPendingViewState();
				}

		function onSetcanrevealinexplorer(enabled) {
			canRevealInExplorer = enabled;
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
		id: persistImageViewStateTimer
		interval: 180
		repeat: false
		onTriggered: saveCurrentImageViewStateNow()
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
		onActivated: copyImageAction()
	}

	Shortcut {
		sequence: "PgUp"
		context: Qt.WindowShortcut
		onActivated: prevAction()
	}

	Shortcut {
		sequence: "PgDown"
		context: Qt.WindowShortcut
		onActivated: nextAction()
	}

	Shortcut {
		sequence: "Space"
		context: Qt.WindowShortcut
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

	onClosing: {
		saveCurrentImageViewStateNow();
	}

	Component.onCompleted: {
		refreshRecentImagePaths();
	}

	Rectangle {
		anchors.fill: parent
		color: "#000000"

		Rectangle {
			anchors.fill: parent
			visible: prestartCountdownActive
			z: 30
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

		Item {
			id: imageViewport
			anchors.fill: parent
			clip: true

			property real imageScale: 1.0
			property real minImageScale: 1.0
			property real maxImageScale: 8.0
			property real imageOffsetX: 0
			property real imageOffsetY: 0
			property real dragLastX: 0
			property real dragLastY: 0
				property real pendingScale: 1.0
				property real pendingOffsetX: 0
				property real pendingOffsetY: 0
				property int pendingRotation: 0
				property bool pendingHasState: false

			function fittedImageSize() {
				if (width <= 0 || height <= 0) {
					return { w: 0, h: 0 };
				}

				if (img.sourceSize.width <= 0 || img.sourceSize.height <= 0) {
					return { w: width, h: height };
				}

				var fitScale = Math.min(width / img.sourceSize.width, height / img.sourceSize.height);
				return {
					w: img.sourceSize.width * fitScale,
					h: img.sourceSize.height * fitScale
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

				img.width = targetWidth;
				img.height = targetHeight;
				img.x = (width - targetWidth) / 2 + imageOffsetX;
				img.y = (height - targetHeight) / 2 + imageOffsetY;
			}

			function resetView() {
				imageScale = 1.0;
				imageOffsetX = 0;
				imageOffsetY = 0;
				applyImageGeometry();
			}

				function applyPendingViewState() {
					if (img.status !== Image.Ready) {
						return;
					}

					if (pendingHasState) {
						imageScale = Math.max(minImageScale, Math.min(maxImageScale, pendingScale));
						imageOffsetX = pendingOffsetX;
						imageOffsetY = pendingOffsetY;
						curImgRotation = normalizeRightAngle(pendingRotation);
					} else {
						imageScale = 1.0;
						imageOffsetX = 0;
						imageOffsetY = 0;
						curImgRotation = 0;
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
				persistImageViewStateTimer.restart();
			}

			onWidthChanged: applyImageGeometry()
			onHeightChanged: applyImageGeometry()

				Image {
					id: img
					source: curImagePath
				asynchronous: true
				autoTransform: true
				mipmap: true
					smooth: true
					mirror: curImgMirror
					fillMode: Image.PreserveAspectFit
					transform: [
						Scale {
							origin.x: img.width / 2
							origin.y: img.height / 2
							xScale: 1
							yScale: curImgFlipVertical ? -1 : 1
						},
						Rotation {
							origin.x: img.width / 2
							origin.y: img.height / 2
							angle: curImgRotation
						}
					]

				onStatusChanged: {
					if (status === Image.Ready) {
						imageViewport.applyPendingViewState();
					}
				}
			}

				MouseArea {
					anchors.fill: parent
					acceptedButtons: Qt.LeftButton
					hoverEnabled: true
					cursorShape: (pressedButtons & Qt.LeftButton) ? Qt.ClosedHandCursor : Qt.OpenHandCursor

				onPressed: function(mouse) {
					imageViewport.dragLastX = mouse.x;
					imageViewport.dragLastY = mouse.y;
				}

				onPositionChanged: function(mouse) {
					if ((mouse.buttons & Qt.LeftButton) === 0) {
						return;
					}

					imageViewport.imageOffsetX += mouse.x - imageViewport.dragLastX;
					imageViewport.imageOffsetY += mouse.y - imageViewport.dragLastY;
					imageViewport.dragLastX = mouse.x;
					imageViewport.dragLastY = mouse.y;
					imageViewport.applyImageGeometry();
					persistImageViewStateTimer.restart();
				}

					onWheel: function(wheel) {
						imageViewport.zoomAt(wheel.x, wheel.y, wheel.angleDelta.y);
						wheel.accepted = true;
					}

					onDoubleClicked: function(mouse) {
						resetCurrentImageStateAction();
						mouse.accepted = true;
					}
				}
			}

			Frame {
				id: timer
				property bool showOvertimeTwoLine: timerEndMode === "overtime" && timerExpiredHold
				anchors {
					top: parent.top
					right: parent.right
					topMargin: 12
					rightMargin: 12
				}
					width: showOvertimeTwoLine ? 130 : 120
					height: showOvertimeTwoLine ? 78 : 48
				z: 10

				background: Rectangle {
					opacity: 0.5
					color: "#101010"
					radius: 10
				}

					Text {
						anchors.fill: parent
						visible: !timer.showOvertimeTwoLine
						text: timerValue
						font.pixelSize: 24
						color: timerColor
						opacity: shouldBlinkTimerValue() ? (timerBlinkOn ? 1.0 : 0.28) : 1.0
						horizontalAlignment: Text.AlignHCenter
						verticalAlignment: Text.AlignVCenter
					}

				Column {
					anchors.fill: parent
					anchors.margins: 4
					spacing: 0
					visible: timer.showOvertimeTwoLine

							Text {
								width: parent.width
								height: parent.height / 2
								text: formatClock(timerSeconds)
								font.pixelSize: 24
								color: timerColor
								opacity: shouldBlinkTimerValue() ? (timerBlinkOn ? 1.0 : 0.28) : 1.0
								horizontalAlignment: Text.AlignHCenter
								verticalAlignment: Text.AlignVCenter
							}

						Text {
							width: parent.width
							height: parent.height / 2
							text: timerValue
							font.pixelSize: 20
							color: timerColor
							opacity: shouldBlinkTimerValue() ? (timerBlinkOn ? 1.0 : 0.28) : 1.0
							horizontalAlignment: Text.AlignHCenter
						verticalAlignment: Text.AlignVCenter
					}
				}

			MouseArea {
				anchors.fill: parent
				acceptedButtons: Qt.LeftButton

				onClicked: timerClickDelay.restart()
			}
		}

			Frame {
				id: panel
			anchors {
				horizontalCenter: parent.horizontalCenter
				bottom: parent.bottom
				margins: 48
			}
			z: 10
			opacity: hovered ? 0.7 : 0.3

			background: Rectangle {
				color: "#101010"
				radius: 10
			}

				RowLayout {
					anchors.fill: parent
					spacing: 2

					Button {
						id: prevButton
						background: Image { source: "./images/prev.png" }
						onClicked: prevAction()
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
					}

					Button {
						id: prevInFolderButton
						background: Image { source: "./images/prev_in_folder.png" }
						onClicked: prevInFolderAction()
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
					}

					Button {
						id: flipHButton
						text: "H"
						font.pixelSize: 12
						topPadding: 2
						bottomPadding: 2
						leftPadding: 6
						rightPadding: 6
						background: Rectangle {
							radius: 4
							color: "#2A2A2A"
						}
						contentItem: Text {
							text: flipHButton.text
							color: "white"
							font.pixelSize: flipHButton.font.pixelSize
							horizontalAlignment: Text.AlignHCenter
							verticalAlignment: Text.AlignVCenter
						}
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
						onClicked: flipHorizontalAction()
					}

					Button {
						id: flipVButton
						text: "V"
						font.pixelSize: 12
						topPadding: 2
						bottomPadding: 2
						leftPadding: 6
						rightPadding: 6
						background: Rectangle {
							radius: 4
							color: "#2A2A2A"
						}
						contentItem: Text {
							text: flipVButton.text
							color: "white"
							font.pixelSize: flipVButton.font.pixelSize
							horizontalAlignment: Text.AlignHCenter
							verticalAlignment: Text.AlignVCenter
						}
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
						onClicked: flipVerticalAction()
					}

					Button {
						id: rotatePlusButton
						text: "+90"
						font.pixelSize: 12
						topPadding: 2
						bottomPadding: 2
						leftPadding: 6
						rightPadding: 6
						background: Rectangle {
							radius: 4
							color: "#2A2A2A"
						}
						contentItem: Text {
							text: rotatePlusButton.text
							color: "white"
							font.pixelSize: rotatePlusButton.font.pixelSize
							horizontalAlignment: Text.AlignHCenter
							verticalAlignment: Text.AlignVCenter
						}
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
						onClicked: rotateClockwiseAction()
					}

					Button {
						id: rotateMinusButton
						text: "-90"
						font.pixelSize: 12
						topPadding: 2
						bottomPadding: 2
						leftPadding: 6
						rightPadding: 6
						background: Rectangle {
							radius: 4
							color: "#2A2A2A"
						}
						contentItem: Text {
							text: rotateMinusButton.text
							color: "white"
							font.pixelSize: rotateMinusButton.font.pixelSize
							horizontalAlignment: Text.AlignHCenter
							verticalAlignment: Text.AlignVCenter
						}
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
						onClicked: rotateCounterClockwiseAction()
					}

					Button {
						id: nextInFolderButton
						background: Image { source: "./images/next_in_folder.png" }
						onClicked: nextInFolderAction()
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
					}

					Button {
						id: nextButton
						background: Image { source: "./images/next.png" }
						onClicked: nextAction()
						opacity: pressed ? 1 : hovered ? 0.8 : 0.2
					}
				}
			}

		MouseArea {
			anchors.fill: parent
			z: 12
			acceptedButtons: Qt.RightButton
			propagateComposedEvents: true

			onPressed: function(mouse) {
				imageContextMenu.x = mouse.x;
				imageContextMenu.y = mouse.y;
				imageContextMenu.open();
				mouse.accepted = true;
			}
		}

		Menu {
			id: imageContextMenu
			delegate: MenuItem {
				implicitHeight: 20
				topPadding: 0
				bottomPadding: 0
				leftPadding: 6
				rightPadding: 6
				font.pixelSize: 12
			}

			MenuItem {
				height: 20
				text: "Reset Timer"
				onTriggered: resetTimerAction()
			}

			MenuItem {
				id: randomPlayMenuItem
				height: 20
				text: ""
				contentItem: RowLayout {
					anchors.fill: parent
					anchors.leftMargin: 6
					anchors.rightMargin: 6
					spacing: 6

					Text {
						text: "Random Play"
						color: randomPlayMenuItem.enabled
							? (randomPlayMenuItem.highlighted
								? randomPlayMenuItem.palette.highlightedText
								: randomPlayMenuItem.palette.text)
							: randomPlayMenuItem.palette.mid
						font.pixelSize: 12
						elide: Text.ElideRight
						verticalAlignment: Text.AlignVCenter
						Layout.fillWidth: true
					}

					Text {
						visible: playModeValue === "RND"
						text: "✓"
						color: randomPlayMenuItem.highlighted
							? randomPlayMenuItem.palette.highlightedText
							: randomPlayMenuItem.palette.text
						font.pixelSize: 10
						verticalAlignment: Text.AlignVCenter
					}
				}
				onTriggered: togglePlayModeAction()
			}

			MenuItem {
				id: stayOnTopMenuItem
				height: 20
				text: ""
				contentItem: RowLayout {
					anchors.fill: parent
					anchors.leftMargin: 6
					anchors.rightMargin: 6
					spacing: 6

					Text {
						text: "Stay On Top"
						color: stayOnTopMenuItem.enabled
							? (stayOnTopMenuItem.highlighted
								? stayOnTopMenuItem.palette.highlightedText
								: stayOnTopMenuItem.palette.text)
							: stayOnTopMenuItem.palette.mid
						font.pixelSize: 12
						elide: Text.ElideRight
						verticalAlignment: Text.AlignVCenter
						Layout.fillWidth: true
					}

					Text {
						visible: stayOnTop
						text: "✓"
						color: stayOnTopMenuItem.highlighted
							? stayOnTopMenuItem.palette.highlightedText
							: stayOnTopMenuItem.palette.text
						font.pixelSize: 10
						verticalAlignment: Text.AlignVCenter
					}
				}
				onTriggered: toggleStayOnTopAction()
			}

			MenuItem {
				height: 20
				text: "Copy Image"
				onTriggered: copyImageAction()
			}

			MenuItem {
				height: 20
				text: "Copy Image Path"
				onTriggered: copyImagePathAction()
			}

			MenuItem {
				height: 20
				visible: canRevealInExplorer
				text: "Show In File Explorer"
				onTriggered: revealInExplorerAction()
			}

			MenuItem {
				height: 20
				text: "Reset Current Image State"
				onTriggered: resetCurrentImageStateAction()
			}
		}

		Popup {
			id: timerEditPopup
			modal: true
			focus: true
			width: 240
			height: 136
			x: parent.width - width - 12
			y: timer.y + timer.height + 8
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
								timerEditApplied = true;
								applyTimerValueAction(text);
								timerEditPopup.close();
							}
						}
				}

				RowLayout {
					Layout.fillWidth: true
					spacing: 8

					Item { Layout.fillWidth: true }

					Button {
						text: "Cancel"
						onClicked: {
							timerEditPopup.close();
							showActionToast("Timer update canceled");
						}
					}

						Button {
							text: "Apply"
							onClicked: {
								if (timerEditInput.acceptableInput && timerEditInput.text.length > 0) {
									timerEditApplied = true;
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
					if (timerEditPausedByPopup) {
						backend.pause();
					}
					timerEditPausedByPopup = false;
					timerEditApplied = false;
				}
			}

			Rectangle {
			id: actionToast
			visible: false
			opacity: 0
			z: 50
			anchors.horizontalCenter: parent.horizontalCenter
			anchors.bottom: parent.bottom
			anchors.bottomMargin: 34
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
