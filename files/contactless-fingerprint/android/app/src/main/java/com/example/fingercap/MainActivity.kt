package com.example.fingercap

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.RectF
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.SurfaceTexture
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CameraMetadata
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.params.StreamConfigurationMap
import android.media.ImageReader
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.util.Base64
import android.util.Log
import android.util.Size
import android.view.Gravity
import android.view.Surface
import android.view.TextureView
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.drawerlayout.widget.DrawerLayout
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.SimpleDateFormat
import java.util.Locale
import kotlin.math.sqrt

class MainActivity : AppCompatActivity() {

    private lateinit var drawerLayout: DrawerLayout
    private lateinit var viewFinder: TextureView
    private lateinit var captureOverlay: CaptureOverlayView
    private lateinit var personIdInput: EditText
    private lateinit var personNameInput: EditText
    private lateinit var thresholdInput: EditText
    private lateinit var modeGroup: RadioGroup
    private lateinit var statusText: TextView
    private lateinit var debugText: TextView
    private lateinit var modeChip: TextView
    private lateinit var showGuideCheck: CheckBox
    private lateinit var showStatsCheck: CheckBox

    private lateinit var cameraManager: CameraManager
    private lateinit var matcherStore: FingerprintStore
    private lateinit var cameraThread: HandlerThread
    private lateinit var cameraHandler: Handler

    private var cameraDevice: CameraDevice? = null
    private var captureSession: CameraCaptureSession? = null
    private var previewRequestBuilder: CaptureRequest.Builder? = null
    private var imageReader: ImageReader? = null
    private var currentCameraId: String? = null
    private var previewSize: Size = Size(1280, 720)
    private var sensorOrientation: Int = 90
    private var isCapturing = false
    private var lastDebugInfo: DebugInfo? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        drawerLayout = findViewById(R.id.drawerLayout)
        viewFinder = findViewById(R.id.viewFinder)
        captureOverlay = findViewById(R.id.captureOverlay)
        personIdInput = findViewById(R.id.personIdInput)
        personNameInput = findViewById(R.id.personNameInput)
        thresholdInput = findViewById(R.id.thresholdInput)
        modeGroup = findViewById(R.id.modeGroup)
        statusText = findViewById(R.id.statusText)
        debugText = findViewById(R.id.debugText)
        modeChip = findViewById(R.id.modeChip)
        showGuideCheck = findViewById(R.id.showGuideCheck)
        showStatsCheck = findViewById(R.id.showStatsCheck)
        findViewById<Button>(R.id.menuButton).setOnClickListener {
            drawerLayout.openDrawer(Gravity.START)
        }
        findViewById<Button>(R.id.captureButton).setOnClickListener { capturePhoto() }

        matcherStore = FingerprintStore(this)
        cameraManager = getSystemService(Context.CAMERA_SERVICE) as CameraManager
        showGuideCheck.setOnCheckedChangeListener { _, checked ->
            captureOverlay.showGuide = checked
        }
        showStatsCheck.setOnCheckedChangeListener { _, _ ->
            renderDebugInfo(lastDebugInfo)
        }

        viewFinder.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
            override fun onSurfaceTextureAvailable(surface: SurfaceTexture, width: Int, height: Int) {
                if (hasCameraPermission()) {
                    openCamera()
                }
            }

            override fun onSurfaceTextureSizeChanged(surface: SurfaceTexture, width: Int, height: Int) {
                configureTransform(width, height)
            }
            override fun onSurfaceTextureDestroyed(surface: SurfaceTexture): Boolean = true
            override fun onSurfaceTextureUpdated(surface: SurfaceTexture) = Unit
        }

        modeGroup.setOnCheckedChangeListener { _, checkedId ->
            val verifyMode = checkedId == R.id.verifyMode
            personNameInput.isEnabled = !verifyMode
            personNameInput.alpha = if (verifyMode) 0.5f else 1f
            modeChip.text = if (verifyMode) "VERIFY" else "REGISTER"
            updateStatus(if (verifyMode) "Verify mode ready" else "Register mode ready")
        }
    }

    override fun onResume() {
        super.onResume()
        startCameraThread()
        if (hasCameraPermission()) {
            if (viewFinder.isAvailable) {
                openCamera()
            }
        } else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQUEST_CODE_CAMERA)
        }
    }

    override fun onPause() {
        closeCamera()
        stopCameraThread()
        super.onPause()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_CODE_CAMERA && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            if (viewFinder.isAvailable) {
                openCamera()
            }
        } else {
            updateStatus("Camera permission denied")
        }
    }

    private fun hasCameraPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
    }

    private fun startCameraThread() {
        cameraThread = HandlerThread("FingerCapCamera").apply { start() }
        cameraHandler = Handler(cameraThread.looper)
    }

    private fun stopCameraThread() {
        if (::cameraThread.isInitialized) {
            cameraThread.quitSafely()
            cameraThread.join()
        }
    }

    private fun openCamera() {
        val cameraId = findBackCameraId() ?: run {
            updateStatus("No back camera found")
            return
        }
        currentCameraId = cameraId
        setupImageReader(cameraId)

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        cameraManager.openCamera(cameraId, object : CameraDevice.StateCallback() {
            override fun onOpened(camera: CameraDevice) {
                cameraDevice = camera
                createPreviewSession()
                enableTorch(true)
            }

            override fun onDisconnected(camera: CameraDevice) {
                camera.close()
                cameraDevice = null
                updateStatus("Camera disconnected")
            }

            override fun onError(camera: CameraDevice, error: Int) {
                camera.close()
                cameraDevice = null
                updateStatus("Camera error: $error")
            }
        }, cameraHandler)
    }

    private fun findBackCameraId(): String? {
        for (cameraId in cameraManager.cameraIdList) {
            val chars = cameraManager.getCameraCharacteristics(cameraId)
            if (chars.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK) {
                val map = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
                previewSize = choosePreviewSize(map)
                sensorOrientation = chars.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 90
                return cameraId
            }
        }
        return null
    }

    private fun choosePreviewSize(map: StreamConfigurationMap?): Size {
        val sizes = map?.getOutputSizes(SurfaceTexture::class.java) ?: return Size(1280, 720)
        return sizes
            .filter { it.width <= 1920 && it.height <= 1080 }
            .maxByOrNull { it.width * it.height }
            ?: sizes.first()
    }

    private fun setupImageReader(cameraId: String) {
        val map = cameraManager.getCameraCharacteristics(cameraId)
            .get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
        val captureSize = map?.getOutputSizes(ImageFormat.JPEG)
            ?.filter { it.width <= 1920 && it.height <= 1920 }
            ?.maxByOrNull { it.width * it.height }
            ?: Size(1280, 720)

        imageReader?.close()
        imageReader = ImageReader.newInstance(captureSize.width, captureSize.height, ImageFormat.JPEG, 2).apply {
            setOnImageAvailableListener({ reader ->
                val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
                val buffer = image.planes[0].buffer
                val bytes = ByteArray(buffer.remaining())
                buffer.get(bytes)
                image.close()
                handleCapturedImage(bytes)
            }, cameraHandler)
        }
    }

    private fun createPreviewSession() {
        val texture = viewFinder.surfaceTexture ?: return
        texture.setDefaultBufferSize(previewSize.width, previewSize.height)
        val previewSurface = Surface(texture)
        val captureSurface = imageReader?.surface ?: return
        val camera = cameraDevice ?: return

        previewRequestBuilder = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
            addTarget(previewSurface)
            set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
            set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
            set(CaptureRequest.FLASH_MODE, CameraMetadata.FLASH_MODE_TORCH)
        }

        camera.createCaptureSession(
            listOf(previewSurface, captureSurface),
            object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    captureSession = session
                    session.setRepeatingRequest(previewRequestBuilder!!.build(), null, cameraHandler)
                    configureTransform(viewFinder.width, viewFinder.height)
                    updateStatus("Camera ready. Torch enabled.")
                }

                override fun onConfigureFailed(session: CameraCaptureSession) {
                    updateStatus("Preview configuration failed")
                }
            },
            cameraHandler
        )
    }

    private fun capturePhoto() {
        if (isCapturing) return
        val camera = cameraDevice ?: run {
            updateStatus("Camera not ready")
            return
        }
        val captureSurface = imageReader?.surface ?: run {
            updateStatus("Capture surface not ready")
            return
        }

        val personId = personIdInput.text.toString().trim()
        if (personId.isEmpty()) {
            updateStatus("Enter a person ID first")
            return
        }

        isCapturing = true
        updateStatus("Capturing...")

        val request = camera.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
            addTarget(captureSurface)
            set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
            set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
            set(CaptureRequest.FLASH_MODE, CameraMetadata.FLASH_MODE_TORCH)
            set(CaptureRequest.JPEG_ORIENTATION, relativeCameraRotation())
        }

        captureSession?.capture(request.build(), object : CameraCaptureSession.CaptureCallback() {}, cameraHandler)
    }

    private fun handleCapturedImage(jpegBytes: ByteArray) {
        val mode = if (modeGroup.checkedRadioButtonId == R.id.verifyMode) CaptureMode.VERIFY else CaptureMode.REGISTER
        val personId = personIdInput.text.toString().trim()
        val displayName = personNameInput.text.toString().trim().ifEmpty { personId }
        val threshold = thresholdInput.text.toString().toFloatOrNull()?.coerceIn(0.1f, 0.99f) ?: DEFAULT_THRESHOLD

        val photoFile = writeCaptureFile(jpegBytes)
        val bitmap = BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.size)
        val cropped = cropToGuide(bitmap)
        val template = FingerprintTemplateExtractor.extract(cropped)
        val debugInfo = FingerprintTemplateExtractor.debugInfo(cropped)
        lastDebugInfo = debugInfo.copy(fileName = photoFile.name)

        runOnUiThread {
            when (mode) {
                CaptureMode.REGISTER -> {
                    matcherStore.save(personId, displayName, template)
                    updateStatus("Registered $displayName ($personId)\nSaved photo: ${photoFile.name}")
                }

                CaptureMode.VERIFY -> {
                    val entry = matcherStore.load(personId)
                    if (entry == null) {
                        updateStatus("No local registration found for $personId")
                    } else {
                        val score = FingerprintTemplateExtractor.compare(template, entry.vector)
                        val verdict = if (score >= threshold) "VERIFIED" else "REJECTED"
                        updateStatus(
                            "$verdict ${entry.name} ($personId)\n" +
                                "score=${"%.3f".format(score)} threshold=${"%.2f".format(threshold)}\n" +
                                "Saved photo: ${photoFile.name}"
                        )
                    }
                }
            }

            renderDebugInfo(lastDebugInfo)
            Toast.makeText(this, "Captured ${photoFile.name}", Toast.LENGTH_SHORT).show()
            isCapturing = false
        }
    }

    private fun cropToGuide(bitmap: Bitmap): Bitmap {
        val guide = captureOverlay.guideRect()
        val viewWidth = viewFinder.width.toFloat().coerceAtLeast(1f)
        val viewHeight = viewFinder.height.toFloat().coerceAtLeast(1f)
        val scale = maxOf(bitmap.width / viewWidth, bitmap.height / viewHeight)

        val cropWidth = (guide.width() * scale).toInt().coerceIn(1, bitmap.width)
        val cropHeight = (guide.height() * scale).toInt().coerceIn(1, bitmap.height)
        val cropLeft = ((bitmap.width - cropWidth) / 2f).toInt().coerceAtLeast(0)
        val cropTop = ((bitmap.height - cropHeight) / 2f).toInt().coerceAtLeast(0)

        val safeWidth = minOf(cropWidth, bitmap.width - cropLeft)
        val safeHeight = minOf(cropHeight, bitmap.height - cropTop)
        return Bitmap.createBitmap(bitmap, cropLeft, cropTop, safeWidth, safeHeight)
    }

    private fun writeCaptureFile(jpegBytes: ByteArray): File {
        val dir = File(filesDir, "captures").apply { mkdirs() }
        val name = SimpleDateFormat("yyyy-MM-dd-HH-mm-ss-SSS", Locale.US)
            .format(System.currentTimeMillis()) + "_finger.jpg"
        val file = File(dir, name)
        file.writeBytes(jpegBytes)
        return file
    }

    private fun enableTorch(enabled: Boolean) {
        val cameraId = currentCameraId ?: return
        val hasFlash = cameraManager.getCameraCharacteristics(cameraId)
            .get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
        if (!hasFlash) {
            updateStatus("Camera ready, but no flash unit detected")
            return
        }
        try {
            cameraManager.setTorchMode(cameraId, enabled)
        } catch (t: Throwable) {
            Log.w(TAG, "Torch control failed", t)
        }
    }

    private fun closeCamera() {
        enableTorch(false)
        captureSession?.close()
        captureSession = null
        cameraDevice?.close()
        cameraDevice = null
        imageReader?.close()
        imageReader = null
    }

    private fun updateStatus(message: String) {
        runOnUiThread {
            statusText.text = message
        }
    }

    private fun renderDebugInfo(info: DebugInfo?) {
        if (!showStatsCheck.isChecked || info == null) {
            debugText.text = "Preview stats hidden."
            return
        }
        debugText.text =
            "file=${info.fileName}\n" +
            "crop=${info.cropWidth}x${info.cropHeight}\n" +
            "aspect=${"%.2f".format(info.aspectRatio)}\n" +
            "brightness=${"%.3f".format(info.brightness)}\n" +
            "contrast=${"%.3f".format(info.contrast)}\n" +
            "edgeEnergy=${"%.3f".format(info.edgeEnergy)}"
    }

    private fun configureTransform(viewWidth: Int, viewHeight: Int) {
        if (previewSize.width == 0 || previewSize.height == 0 || viewWidth == 0 || viewHeight == 0) return

        val matrix = Matrix()
        val viewRect = RectF(0f, 0f, viewWidth.toFloat(), viewHeight.toFloat())
        val centerX = viewRect.centerX()
        val centerY = viewRect.centerY()

        // Camera2 supplies the normal portrait buffer at launch. Only compensate when
        // the display itself rotates, matching the platform Camera2 sample behavior.
        when (viewFinder.display?.rotation ?: Surface.ROTATION_0) {
            Surface.ROTATION_90, Surface.ROTATION_270 -> {
                val bufferRect = RectF(0f, 0f, previewSize.height.toFloat(), previewSize.width.toFloat())
                bufferRect.offset(centerX - bufferRect.centerX(), centerY - bufferRect.centerY())
                matrix.setRectToRect(viewRect, bufferRect, Matrix.ScaleToFit.FILL)
                val scale = maxOf(
                    viewHeight.toFloat() / previewSize.height.toFloat(),
                    viewWidth.toFloat() / previewSize.width.toFloat()
                )
                matrix.postScale(scale, scale, centerX, centerY)
                val degrees = if (viewFinder.display.rotation == Surface.ROTATION_90) -90f else 90f
                matrix.postRotate(degrees, centerX, centerY)
            }
            Surface.ROTATION_180 -> matrix.postRotate(180f, centerX, centerY)
        }
        viewFinder.setTransform(matrix)
    }

    /** Maps the camera sensor's native orientation to the display's current rotation. */
    private fun relativeCameraRotation(): Int {
        val displayDegrees = when (viewFinder.display?.rotation ?: Surface.ROTATION_0) {
            Surface.ROTATION_90 -> 90
            Surface.ROTATION_180 -> 180
            Surface.ROTATION_270 -> 270
            else -> 0
        }
        return (sensorOrientation - displayDegrees + 360) % 360
    }

    companion object {
        private const val TAG = "FingerCap"
        private const val REQUEST_CODE_CAMERA = 10
        private const val DEFAULT_THRESHOLD = 0.82f
    }
}

private enum class CaptureMode {
    REGISTER,
    VERIFY
}

private data class StoredFingerprint(
    val id: String,
    val name: String,
    val vector: FloatArray
)

private class FingerprintStore(context: Context) {
    private val prefs = context.getSharedPreferences("finger_registry", Context.MODE_PRIVATE)

    fun save(id: String, name: String, vector: FloatArray) {
        prefs.edit()
            .putString(templateKey(id), encode(vector))
            .putString(nameKey(id), name)
            .apply()
    }

    fun load(id: String): StoredFingerprint? {
        val encoded = prefs.getString(templateKey(id), null) ?: return null
        return StoredFingerprint(
            id = id,
            name = prefs.getString(nameKey(id), id) ?: id,
            vector = decode(encoded)
        )
    }

    private fun templateKey(id: String) = "template_$id"
    private fun nameKey(id: String) = "name_$id"

    private fun encode(vector: FloatArray): String {
        val bytes = ByteBuffer.allocate(vector.size * 4)
            .order(ByteOrder.LITTLE_ENDIAN)
        vector.forEach { bytes.putFloat(it) }
        return Base64.encodeToString(bytes.array(), Base64.NO_WRAP)
    }

    private fun decode(encoded: String): FloatArray {
        val raw = Base64.decode(encoded, Base64.NO_WRAP)
        val buffer = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
        val result = FloatArray(raw.size / 4)
        for (i in result.indices) {
            result[i] = buffer.getFloat()
        }
        return result
    }
}

private object FingerprintTemplateExtractor {
    private const val TEMPLATE_SIZE = 32

    fun extract(bitmap: Bitmap): FloatArray {
        val normalized = Bitmap.createScaledBitmap(centerCrop(bitmap), TEMPLATE_SIZE, TEMPLATE_SIZE, true)
        val pixels = IntArray(TEMPLATE_SIZE * TEMPLATE_SIZE)
        normalized.getPixels(pixels, 0, TEMPLATE_SIZE, 0, 0, TEMPLATE_SIZE, TEMPLATE_SIZE)

        val grayscale = FloatArray(pixels.size)
        for (i in pixels.indices) {
            val color = pixels[i]
            val r = (color shr 16) and 0xff
            val g = (color shr 8) and 0xff
            val b = color and 0xff
            grayscale[i] = (0.299f * r + 0.587f * g + 0.114f * b) / 255f
        }

        val mean = grayscale.average().toFloat()
        val variance = grayscale.fold(0f) { acc, value ->
            val centered = value - mean
            acc + centered * centered
        } / grayscale.size
        val std = sqrt(variance).coerceAtLeast(1e-4f)

        val template = FloatArray(TEMPLATE_SIZE * TEMPLATE_SIZE)
        for (y in 0 until TEMPLATE_SIZE) {
            for (x in 0 until TEMPLATE_SIZE) {
                val idx = y * TEMPLATE_SIZE + x
                val gx = if (x == TEMPLATE_SIZE - 1) 0f else grayscale[idx + 1] - grayscale[idx]
                val gy = if (y == TEMPLATE_SIZE - 1) 0f else grayscale[idx + TEMPLATE_SIZE] - grayscale[idx]
                template[idx] = (gx + gy + (grayscale[idx] - mean)) / std
            }
        }

        val norm = sqrt(template.fold(0f) { acc, value -> acc + value * value }).coerceAtLeast(1e-4f)
        return FloatArray(template.size) { i -> template[i] / norm }
    }

    fun compare(left: FloatArray, right: FloatArray): Float {
        val size = minOf(left.size, right.size)
        var dot = 0f
        for (i in 0 until size) {
            dot += left[i] * right[i]
        }
        return ((dot + 1f) / 2f).coerceIn(0f, 1f)
    }

    fun debugInfo(bitmap: Bitmap): DebugInfo {
        val scaled = Bitmap.createScaledBitmap(bitmap, TEMPLATE_SIZE, TEMPLATE_SIZE, true)
        val pixels = IntArray(TEMPLATE_SIZE * TEMPLATE_SIZE)
        scaled.getPixels(pixels, 0, TEMPLATE_SIZE, 0, 0, TEMPLATE_SIZE, TEMPLATE_SIZE)
        var sum = 0f
        var edge = 0f
        val gray = FloatArray(pixels.size)
        for (i in pixels.indices) {
            val color = pixels[i]
            val r = (color shr 16) and 0xff
            val g = (color shr 8) and 0xff
            val b = color and 0xff
            val value = (0.299f * r + 0.587f * g + 0.114f * b) / 255f
            gray[i] = value
            sum += value
        }
        val mean = sum / gray.size
        var variance = 0f
        for (y in 0 until TEMPLATE_SIZE) {
            for (x in 0 until TEMPLATE_SIZE) {
                val idx = y * TEMPLATE_SIZE + x
                val v = gray[idx]
                variance += (v - mean) * (v - mean)
                if (x < TEMPLATE_SIZE - 1) edge += kotlin.math.abs(v - gray[idx + 1])
                if (y < TEMPLATE_SIZE - 1) edge += kotlin.math.abs(v - gray[idx + TEMPLATE_SIZE])
            }
        }
        return DebugInfo(
            cropWidth = bitmap.width,
            cropHeight = bitmap.height,
            aspectRatio = bitmap.height.toFloat() / bitmap.width.toFloat(),
            brightness = mean,
            contrast = sqrt(variance / gray.size),
            edgeEnergy = edge / gray.size
        )
    }

    private fun centerCrop(bitmap: Bitmap): Bitmap {
        val side = minOf(bitmap.width, bitmap.height)
        val left = (bitmap.width - side) / 2
        val top = (bitmap.height - side) / 2
        val cropped = Bitmap.createBitmap(bitmap, left, top, side, side)

        val inset = (side * 0.10f).toInt().coerceAtLeast(1)
        val rect = Rect(inset, inset, cropped.width - inset, cropped.height - inset)
        return Bitmap.createBitmap(cropped, rect.left, rect.top, rect.width(), rect.height())
    }
}

private data class DebugInfo(
    val cropWidth: Int,
    val cropHeight: Int,
    val aspectRatio: Float,
    val brightness: Float,
    val contrast: Float,
    val edgeEnergy: Float,
    val fileName: String = ""
)
