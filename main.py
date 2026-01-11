from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from android.permissions import request_permissions, Permission
from jnius import autoclass, cast
from datetime import datetime
import threading

# Android Java classes
PythonActivity = autoclass('org.kivy.android.PythonActivity')
Intent = autoclass('android.content.Intent')
Environment = autoclass('android.os.Environment')
File = autoclass('java.io.File')
FileOutputStream = autoclass('java.io.FileOutputStream')
Bitmap = autoclass('android.graphics.Bitmap')
CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
MediaProjectionManager = autoclass('android.media.projection.MediaProjectionManager')
Context = autoclass('android.content.Context')
ImageReader = autoclass('android.media.ImageReader')
PixelFormat = autoclass('android.graphics.PixelFormat')
DisplayMetrics = autoclass('android.util.DisplayMetrics')
WindowManager = autoclass('android.view.WindowManager')
Build = autoclass('android.os.Build')
VirtualDisplay = autoclass('android.hardware.display.VirtualDisplay')
ContentValues = autoclass('android.content.ContentValues')
MediaStore = autoclass('android.provider.MediaStore')
Uri = autoclass('android.net.Uri')
ByteBuffer = autoclass('java.nio.ByteBuffer')

class ScreenshotApp(App):
    REQUEST_CODE = 1000
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_tap_time = 0
        self.tap_count = 0
        self.double_tap_threshold = 0.3
        self.media_projection = None
        self.image_reader = None
        self.virtual_display = None
        self.is_capturing = False
        
    def build(self):
        # Request permissions for Android 14
        request_permissions([
            Permission.READ_MEDIA_IMAGES,
            Permission.FOREGROUND_SERVICE,
            Permission.FOREGROUND_SERVICE_MEDIA_PROJECTION
        ])
        
        layout = FloatLayout()
        
        # Status label
        self.label = Label(
            text='Tap "Start" to enable screenshot capture',
            size_hint=(1, 0.15),
            pos_hint={'center_x': 0.5, 'top': 1}
        )
        layout.add_widget(self.label)
        
        # Start button
        self.start_btn = Button(
            text='Start Screenshot Service',
            size_hint=(0.8, 0.1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.start_btn.bind(on_press=self.request_screenshot_permission)
        layout.add_widget(self.start_btn)
        
        # Bind touch events
        Window.bind(on_touch_down=self.on_touch_down)
        
        # Bind activity result
        self.bind_activity_result()
        
        return layout
    
    def bind_activity_result(self):
        """Set up activity result callback"""
        activity = PythonActivity.mActivity
        
        # Create a custom runnable to handle results
        original_on_activity_result = activity.onActivityResult
        
        def new_on_activity_result(requestCode, resultCode, data):
            if requestCode == self.REQUEST_CODE:
                Activity = autoclass('android.app.Activity')
                if resultCode == Activity.RESULT_OK:
                    self.start_media_projection(resultCode, data)
                else:
                    self.label.text = 'Permission denied. Tap Start to try again.'
            
            # Call original method if it exists
            if original_on_activity_result:
                try:
                    original_on_activity_result(requestCode, resultCode, data)
                except:
                    pass
        
        activity.onActivityResult = new_on_activity_result
    
    def request_screenshot_permission(self, instance):
        """Request MediaProjection permission"""
        try:
            activity = PythonActivity.mActivity
            projection_manager = cast(
                MediaProjectionManager,
                activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
            )
            
            # Create screen capture intent
            capture_intent = projection_manager.createScreenCaptureIntent()
            activity.startActivityForResult(capture_intent, self.REQUEST_CODE)
            
            self.label.text = 'Grant permission in the dialog...'
            
        except Exception as e:
            self.label.text = f'Error requesting permission: {str(e)}'
    
    def start_media_projection(self, result_code, data):
        """Initialize MediaProjection after permission granted"""
        try:
            activity = PythonActivity.mActivity
            projection_manager = cast(
                MediaProjectionManager,
                activity.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
            )
            
            # Get MediaProjection
            self.media_projection = projection_manager.getMediaProjection(result_code, data)
            
            # Set up ImageReader
            self.setup_image_reader()
            
            self.label.text = 'Ready! Double-tap center to screenshot'
            self.start_btn.text = 'Service Active'
            self.start_btn.disabled = True
            
        except Exception as e:
            self.label.text = f'Error starting projection: {str(e)}'
    
    def setup_image_reader(self):
        """Set up ImageReader for capturing screenshots"""
        try:
            activity = PythonActivity.mActivity
            window_manager = cast(
                WindowManager,
                activity.getSystemService(Context.WINDOW_SERVICE)
            )
            
            # Get display metrics
            metrics = DisplayMetrics()
            display = window_manager.getDefaultDisplay()
            display.getRealMetrics(metrics)
            
            self.screen_width = metrics.widthPixels
            self.screen_height = metrics.heightPixels
            self.screen_density = metrics.densityDpi
            
            # Create ImageReader
            self.image_reader = ImageReader.newInstance(
                self.screen_width,
                self.screen_height,
                PixelFormat.RGBA_8888,
                2
            )
            
        except Exception as e:
            self.label.text = f'Error setting up reader: {str(e)}'
    
    def on_touch_down(self, instance, touch):
        """Handle touch events for double-tap detection"""
        if not self.media_projection or self.is_capturing:
            return
        
        # Get screen dimensions
        screen_width = Window.width
        screen_height = Window.height
        
        # Define center area (30% of screen from center)
        center_x = screen_width / 2
        center_y = screen_height / 2
        tolerance_x = screen_width * 0.15
        tolerance_y = screen_height * 0.15
        
        # Check if tap is in center area
        is_center = (
            abs(touch.x - center_x) < tolerance_x and
            abs(touch.y - center_y) < tolerance_y
        )
        
        if is_center:
            current_time = Clock.get_time()
            
            # Check if this is a double tap
            if current_time - self.last_tap_time < self.double_tap_threshold:
                self.tap_count += 1
                if self.tap_count == 1:  # Second tap
                    self.take_screenshot()
                    self.tap_count = 0
            else:
                self.tap_count = 0
            
            self.last_tap_time = current_time
    
    def take_screenshot(self):
        """Capture screenshot using MediaProjection"""
        if self.is_capturing:
            return
        
        self.is_capturing = True
        self.label.text = 'Capturing screenshot...'
        
        # Run in thread to avoid blocking UI
        threading.Thread(target=self._capture_screen).start()
    
    def _capture_screen(self):
        """Actual screenshot capture logic"""
        try:
            activity = PythonActivity.mActivity
            
            # Create virtual display
            self.virtual_display = self.media_projection.createVirtualDisplay(
                "ScreenCapture",
                self.screen_width,
                self.screen_height,
                self.screen_density,
                0,  # flags
                self.image_reader.getSurface(),
                None,
                None
            )
            
            # Small delay to ensure frame is ready
            import time
            time.sleep(0.1)
            
            # Get the latest image
            image = self.image_reader.acquireLatestImage()
            
            if image is None:
                Clock.schedule_once(lambda dt: setattr(self.label, 'text', 'Failed to capture'), 0)
                self.is_capturing = False
                return
            
            # Get image data
            planes = image.getPlanes()
            buffer = planes[0].getBuffer()
            pixel_stride = planes[0].getPixelStride()
            row_stride = planes[0].getRowStride()
            row_padding = row_stride - pixel_stride * self.screen_width
            
            # Create bitmap
            bitmap = Bitmap.createBitmap(
                self.screen_width + row_padding // pixel_stride,
                self.screen_height,
                Bitmap.Config.ARGB_8888
            )
            bitmap.copyPixelsFromBuffer(buffer)
            
            # Close image
            image.close()
            
            # Stop virtual display
            if self.virtual_display:
                self.virtual_display.release()
                self.virtual_display = None
            
            # Save the bitmap
            Clock.schedule_once(lambda dt: self.save_screenshot(bitmap), 0)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self.label, 'text', f'Capture error: {str(e)}'), 0)
            self.is_capturing = False
    
    def save_screenshot(self, bitmap):
        """Save bitmap to Pictures/Screenshots using MediaStore (Android 14 compatible)"""
        try:
            activity = PythonActivity.mActivity
            resolver = activity.getContentResolver()
            
            # Prepare content values
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'screenshot_{timestamp}.png'
            
            values = ContentValues()
            values.put(MediaStore.Images.Media.DISPLAY_NAME, filename)
            values.put(MediaStore.Images.Media.MIME_TYPE, 'image/png')
            values.put(MediaStore.Images.Media.RELATIVE_PATH, 'Pictures/Screenshots')
            
            # Insert into MediaStore
            uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            
            if uri:
                # Open output stream
                output_stream = resolver.openOutputStream(uri)
                
                # Compress and save bitmap
                bitmap.compress(CompressFormat.PNG, 100, output_stream)
                output_stream.flush()
                output_stream.close()
                
                self.label.text = f'Saved: {filename}'
            else:
                self.label.text = 'Failed to save screenshot'
            
            # Reset after 2 seconds
            Clock.schedule_once(lambda dt: self.reset_label(), 2)
            
        except Exception as e:
            self.label.text = f'Save error: {str(e)}'
        finally:
            self.is_capturing = False
    
    def reset_label(self):
        self.label.text = 'Ready! Double-tap center to screenshot'
    
    def on_stop(self):
        """Clean up when app closes"""
        if self.virtual_display:
            self.virtual_display.release()
        if self.image_reader:
            self.image_reader.close()
        if self.media_projection:
            self.media_projection.stop()

if __name__ == '__main__':
    ScreenshotApp().run()
