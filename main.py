from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from android.permissions import request_permissions, Permission
from jnius import autoclass, cast, PythonJavaClass, java_method
from datetime import datetime
import threading

# Android Java classes
PythonActivity = autoclass('org.kivy.android.PythonActivity')
Intent = autoclass('android.content.Intent')
Settings = autoclass('android.provider.Settings')
Build = autoclass('android.os.Build')
Context = autoclass('android.content.Context')
LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
WindowManager = autoclass('android.view.WindowManager')
PixelFormat = autoclass('android.graphics.PixelFormat')
Gravity = autoclass('android.view.Gravity')
View = autoclass('android.view.View')
Color = autoclass('android.graphics.Color')
KeyEvent = autoclass('android.view.KeyEvent')
CameraManager = autoclass('android.hardware.camera2.CameraManager')
CameraDevice = autoclass('android.hardware.camera2.CameraDevice')
ImageReader = autoclass('android.media.ImageReader')
CaptureRequest = autoclass('android.hardware.camera2.CaptureRequest')
CameraCaptureSession = autoclass('android.hardware.camera2.CameraCaptureSession')
Surface = autoclass('android.view.Surface')
Handler = autoclass('android.os.Handler')
HandlerThread = autoclass('android.os.HandlerThread')
File = autoclass('java.io.File')
FileOutputStream = autoclass('java.io.FileOutputStream')
Bitmap = autoclass('android.graphics.Bitmap')
CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
Environment = autoclass('android.os.Environment')
ContentValues = autoclass('android.content.ContentValues')
MediaStore = autoclass('android.provider.MediaStore')

class VolumeKeyReceiver(PythonJavaClass):
    __javainterfaces__ = ['android/content/BroadcastReceiver']
    __javacontext__ = 'app'
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        if self.callback:
            self.callback()

class CameraApp(App):
    OVERLAY_PERMISSION_CODE = 1234
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.overlay_view = None
        self.window_manager = None
        self.camera_device = None
        self.capture_session = None
        self.image_reader = None
        self.background_thread = None
        self.background_handler = None
        self.volume_press_count = 0
        self.volume_press_time = 0
        self.volume_threshold = 1.0  # 1 second for 3 presses
        
    def build(self):
        # Request permissions
        request_permissions([
            Permission.CAMERA,
            Permission.READ_MEDIA_IMAGES,
            Permission.FOREGROUND_SERVICE,
            Permission.FOREGROUND_SERVICE_CAMERA
        ])
        
        layout = FloatLayout()
        
        # Status label
        self.label = Label(
            text='Camera Capture App',
            size_hint=(1, 0.15),
            pos_hint={'center_x': 0.5, 'top': 1}
        )
        layout.add_widget(self.label)
        
        # Start overlay button
        self.start_btn = Button(
            text='Enable Overlay & Camera',
            size_hint=(0.8, 0.1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.start_btn.bind(on_press=self.request_overlay_permission)
        layout.add_widget(self.start_btn)
        
        # Info label
        info = Label(
            text='Tap center overlay OR press Volume Down 3x quickly',
            size_hint=(1, 0.15),
            pos_hint={'center_x': 0.5, 'bottom': 0},
            font_size='14sp'
        )
        layout.add_widget(info)
        
        # Setup volume key listener
        self.setup_volume_listener()
        
        return layout
    
    def request_overlay_permission(self, instance):
        """Request overlay permission for Android"""
        try:
            activity = PythonActivity.mActivity
            
            # Check if permission is already granted
            if Build.VERSION.SDK_INT >= 23:
                if not Settings.canDrawOverlays(activity):
                    self.label.text = 'Please grant overlay permission...'
                    intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        autoclass('android.net.Uri').parse(f'package:{activity.getPackageName()}')
                    )
                    activity.startActivityForResult(intent, self.OVERLAY_PERMISSION_CODE)
                else:
                    self.start_overlay_and_camera()
            else:
                self.start_overlay_and_camera()
                
        except Exception as e:
            self.label.text = f'Permission error: {str(e)}'
    
    def start_overlay_and_camera(self):
        """Start the overlay service and initialize camera"""
        try:
            # Create overlay
            self.create_overlay()
            
            # Initialize camera
            self.initialize_camera()
            
            self.label.text = 'Overlay active! Tap center or press Vol Down 3x'
            self.start_btn.text = 'Active'
            self.start_btn.disabled = True
            
        except Exception as e:
            self.label.text = f'Start error: {str(e)}'
    
    def create_overlay(self):
        """Create transparent overlay button"""
        try:
            activity = PythonActivity.mActivity
            self.window_manager = cast(
                WindowManager,
                activity.getSystemService(Context.WINDOW_SERVICE)
            )
            
            # Create transparent view
            self.overlay_view = View(activity)
            self.overlay_view.setBackgroundColor(Color.TRANSPARENT)
            
            # Set click listener
            OnClickListener = autoclass('android.view.View$OnClickListener')
            
            class ClickListener(PythonJavaClass):
                __javainterfaces__ = ['android/view/View$OnClickListener']
                
                def __init__(self, callback):
                    super().__init__()
                    self.callback = callback
                
                @java_method('(Landroid/view/View;)V')
                def onClick(self, view):
                    self.callback()
            
            listener = ClickListener(self.take_photo)
            self.overlay_view.setOnClickListener(listener)
            
            # Layout parameters - center of screen, small transparent button
            if Build.VERSION.SDK_INT >= 26:
                layout_type = LayoutParams.TYPE_APPLICATION_OVERLAY
            else:
                layout_type = LayoutParams.TYPE_PHONE
            
            # Small 100x100 transparent button in center
            params = LayoutParams(
                200,  # width (dp)
                200,  # height (dp)
                layout_type,
                LayoutParams.FLAG_NOT_FOCUSABLE | LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT
            )
            params.gravity = Gravity.CENTER
            
            # Add overlay to window
            self.window_manager.addView(self.overlay_view, params)
            
        except Exception as e:
            self.label.text = f'Overlay error: {str(e)}'
    
    def setup_volume_listener(self):
        """Setup volume key listener"""
        try:
            activity = PythonActivity.mActivity
            
            # Override dispatchKeyEvent
            original_dispatch = activity.dispatchKeyEvent
            
            def new_dispatch(event):
                keycode = event.getKeyCode()
                action = event.getAction()
                
                if keycode == KeyEvent.KEYCODE_VOLUME_DOWN and action == KeyEvent.ACTION_DOWN:
                    self.handle_volume_down()
                    return True  # Consume the event
                
                if original_dispatch:
                    try:
                        return original_dispatch(event)
                    except:
                        return False
                return False
            
            activity.dispatchKeyEvent = new_dispatch
            
        except Exception as e:
            print(f'Volume listener error: {str(e)}')
    
    def handle_volume_down(self):
        """Handle volume down button press"""
        current_time = Clock.get_time()
        
        # Reset counter if too much time passed
        if current_time - self.volume_press_time > self.volume_threshold:
            self.volume_press_count = 0
        
        self.volume_press_count += 1
        self.volume_press_time = current_time
        
        # Check if 3 presses detected
        if self.volume_press_count >= 3:
            self.volume_press_count = 0
            Clock.schedule_once(lambda dt: self.take_photo(), 0)
    
    def initialize_camera(self):
        """Initialize camera for front camera capture"""
        try:
            activity = PythonActivity.mActivity
            camera_manager = cast(
                CameraManager,
                activity.getSystemService(Context.CAMERA_SERVICE)
            )
            
            # Get front camera ID
            camera_ids = camera_manager.getCameraIdList()
            front_camera_id = None
            
            CameraCharacteristics = autoclass('android.hardware.camera2.CameraCharacteristics')
            
            for camera_id in camera_ids:
                characteristics = camera_manager.getCameraCharacteristics(camera_id)
                facing = characteristics.get(CameraCharacteristics.LENS_FACING)
                if facing == CameraCharacteristics.LENS_FACING_FRONT:
                    front_camera_id = camera_id
                    break
            
            if not front_camera_id:
                self.label.text = 'Front camera not found'
                return
            
            # Start background thread for camera operations
            self.background_thread = HandlerThread("CameraBackground")
            self.background_thread.start()
            self.background_handler = Handler(self.background_thread.getLooper())
            
            # Setup ImageReader
            self.image_reader = ImageReader.newInstance(1920, 1080, 256, 2)  # JPEG format
            
            # Open camera
            class StateCallback(PythonJavaClass):
                __javainterfaces__ = ['android/hardware/camera2/CameraDevice$StateCallback']
                
                def __init__(self, app):
                    super().__init__()
                    self.app = app
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;)V')
                def onOpened(self, camera):
                    self.app.camera_device = camera
                    Clock.schedule_once(lambda dt: setattr(self.app.label, 'text', 'Camera ready!'), 0)
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;)V')
                def onDisconnected(self, camera):
                    camera.close()
                    self.app.camera_device = None
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;I)V')
                def onError(self, camera, error):
                    camera.close()
                    self.app.camera_device = None
                    Clock.schedule_once(lambda dt: setattr(self.app.label, 'text', f'Camera error: {error}'), 0)
            
            state_callback = StateCallback(self)
            camera_manager.openCamera(front_camera_id, state_callback, self.background_handler)
            
        except Exception as e:
            self.label.text = f'Camera init error: {str(e)}'
    
    def take_photo(self):
        """Capture photo from front camera"""
        if not self.camera_device:
            Clock.schedule_once(lambda dt: setattr(self.label, 'text', 'Camera not ready'), 0)
            return
        
        Clock.schedule_once(lambda dt: setattr(self.label, 'text', 'Taking photo...'), 0)
        threading.Thread(target=self._capture_photo).start()
    
    def _capture_photo(self):
        """Actual photo capture logic"""
        try:
            # Create capture request
            builder = self.camera_device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
            builder.addTarget(self.image_reader.getSurface())
            
            # Create capture session
            class SessionCallback(PythonJavaClass):
                __javainterfaces__ = ['android/hardware/camera2/CameraCaptureSession$StateCallback']
                
                def __init__(self, app, builder):
                    super().__init__()
                    self.app = app
                    self.builder = builder
                
                @java_method('(Landroid/hardware/camera2/CameraCaptureSession;)V')
                def onConfigured(self, session):
                    self.app.capture_session = session
                    
                    class CaptureCallback(PythonJavaClass):
                        __javainterfaces__ = ['android/hardware/camera2/CameraCaptureSession$CaptureCallback']
                        
                        def __init__(self, app):
                            super().__init__()
                            self.app = app
                        
                        @java_method('(Landroid/hardware/camera2/CameraCaptureSession;Landroid/hardware/camera2/CaptureRequest;Landroid/hardware/camera2/TotalCaptureResult;)V')
                        def onCaptureCompleted(self, session, request, result):
                            Clock.schedule_once(lambda dt: self.app.save_image(), 0.5)
                    
                    capture_callback = CaptureCallback(self.app)
                    session.capture(self.builder.build(), capture_callback, self.app.background_handler)
                
                @java_method('(Landroid/hardware/camera2/CameraCaptureSession;)V')
                def onConfigureFailed(self, session):
                    Clock.schedule_once(lambda dt: setattr(self.app.label, 'text', 'Capture failed'), 0)
            
            surfaces = [self.image_reader.getSurface()]
            session_callback = SessionCallback(self, builder)
            self.camera_device.createCaptureSession(surfaces, session_callback, self.background_handler)
            
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self.label, 'text', f'Capture error: {str(e)}'), 0)
    
    def save_image(self):
        """Save captured image to gallery"""
        try:
            image = self.image_reader.acquireLatestImage()
            if not image:
                self.label.text = 'No image captured'
                return
            
            # Get image data
            buffer = image.getPlanes()[0].getBuffer()
            bytes_array = bytearray(buffer.remaining())
            buffer.get(bytes_array)
            
            # Save to MediaStore
            activity = PythonActivity.mActivity
            resolver = activity.getContentResolver()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'front_camera_{timestamp}.jpg'
            
            values = ContentValues()
            values.put(MediaStore.Images.Media.DISPLAY_NAME, filename)
            values.put(MediaStore.Images.Media.MIME_TYPE, 'image/jpeg')
            values.put(MediaStore.Images.Media.RELATIVE_PATH, 'Pictures/FrontCamera')
            
            uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            
            if uri:
                output_stream = resolver.openOutputStream(uri)
                output_stream.write(bytes_array)
                output_stream.flush()
                output_stream.close()
                
                self.label.text = f'Saved: {filename}'
            
            image.close()
            Clock.schedule_once(lambda dt: setattr(self.label, 'text', 'Ready! Tap or Vol Down 3x'), 2)
            
        except Exception as e:
            self.label.text = f'Save error: {str(e)}'
    
    def on_stop(self):
        """Clean up resources"""
        if self.capture_session:
            self.capture_session.close()
        if self.camera_device:
            self.camera_device.close()
        if self.image_reader:
            self.image_reader.close()
        if self.background_thread:
            self.background_thread.quitSafely()
        if self.overlay_view and self.window_manager:
            try:
                self.window_manager.removeView(self.overlay_view)
            except:
                pass

if __name__ == '__main__':
    CameraApp().run()
