#!/usr/bin/env bash

create-dmg \
    --volname "Eversilver installer" \
    --volicon "./app/src-tauri/icons/icon.icns" \
    --background "./app/src-tauri/images/background-dmg.svg" \
    --window-size 540 380 \
    --icon-size 100 \
    --icon "Eversilver.app" 138 225 \
    --hide-extension "Eversilver.app" \
    --app-drop-link 402 225 \
    --no-internet-enable \
    "$1" \
    "$2"
