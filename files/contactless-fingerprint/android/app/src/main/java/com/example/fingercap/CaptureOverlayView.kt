package com.example.fingercap

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View

class CaptureOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private val scrimPaint = Paint().apply {
        color = Color.argb(140, 5, 10, 18)
    }

    private val boxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(230, 225, 245, 255)
        style = Paint.Style.STROKE
        strokeWidth = 5f
    }

    private val cornerPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.argb(255, 120, 220, 255)
        style = Paint.Style.STROKE
        strokeWidth = 9f
    }

    private val labelPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textSize = 38f
    }

    var showGuide: Boolean = true
        set(value) {
            field = value
            invalidate()
        }

    var label: String = "Align fingerprint in box"
        set(value) {
            field = value
            invalidate()
        }

    fun guideRect(): RectF {
        val widthInset = width * 0.12f
        val frameWidth = width - (2f * widthInset)
        val frameHeight = frameWidth * 1.28f
        val left = widthInset
        val top = (height - frameHeight) * 0.42f
        return RectF(left, top, left + frameWidth, top + frameHeight)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (!showGuide) return

        val box = guideRect()
        canvas.drawRect(0f, 0f, width.toFloat(), box.top, scrimPaint)
        canvas.drawRect(0f, box.top, box.left, box.bottom, scrimPaint)
        canvas.drawRect(box.right, box.top, width.toFloat(), box.bottom, scrimPaint)
        canvas.drawRect(0f, box.bottom, width.toFloat(), height.toFloat(), scrimPaint)

        canvas.drawRoundRect(box, 36f, 36f, boxPaint)

        val corner = 42f
        canvas.drawLine(box.left, box.top + corner, box.left, box.top, cornerPaint)
        canvas.drawLine(box.left, box.top, box.left + corner, box.top, cornerPaint)
        canvas.drawLine(box.right - corner, box.top, box.right, box.top, cornerPaint)
        canvas.drawLine(box.right, box.top, box.right, box.top + corner, cornerPaint)
        canvas.drawLine(box.left, box.bottom - corner, box.left, box.bottom, cornerPaint)
        canvas.drawLine(box.left, box.bottom, box.left + corner, box.bottom, cornerPaint)
        canvas.drawLine(box.right - corner, box.bottom, box.right, box.bottom, cornerPaint)
        canvas.drawLine(box.right, box.bottom - corner, box.right, box.bottom, cornerPaint)

        canvas.drawText(label, box.left, box.top - 24f, labelPaint)
    }
}
