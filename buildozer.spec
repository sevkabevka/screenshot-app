[app]

# App name
title = Front Camera Capture

# Package name
package.name = frontcamera

# Package domain
package.domain = org.example

# Source directory
source.dir = .

# Source files
source.include_exts = py,png,jpg,kv,atlas

# Version
version = 0.1

# Requirements
requirements = python3,kivy==2.2.1,pyjnius,android

# Android permissions (Android 14 specific)
android.permissions = android.permission.CAMERA,android.permission.READ_MEDIA_IMAGES,android.permission.FOREGROUND_SERVICE,android.permission.FOREGROUND_SERVICE_CAMERA,android.permission.SYSTEM_ALERT_WINDOW

# Orientation
orientation = portrait

# Android API levels (Android 14 = API 34)
android.api = 34
android.minapi = 26
android.ndk = 25b

# Supported architectures
android.archs = arm64-v8a,armeabi-v7a

# Display mode
fullscreen = 0

# Android features
android.features = android.hardware.camera,android.hardware.camera.front

# Gradle dependencies
android.gradle_dependencies = androidx.core:core:1.12.0

# Enable androidx
android.enable_androidx = True

# Presplash settings (optional)
#presplash.filename = %(source.dir)s/presplash.png

# Icon settings (optional)
#icon.filename = %(source.dir)s/icon.png

[buildozer]

# Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# Display warning if buildozer is run as root
warn_on_root = 1
