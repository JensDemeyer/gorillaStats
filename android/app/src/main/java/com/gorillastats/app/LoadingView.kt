package com.gorillastats.app

import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.os.Handler
import android.os.Looper
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.view.animation.LinearInterpolator
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.math.min

private object Palette {
    val BACKGROUND = Color.parseColor("#0D140E")
    val CARD = Color.parseColor("#1C281E")
    val BORDER = Color.parseColor("#2D3F30")
    val BORDER_LIGHT = Color.parseColor("#3A5040")
    val GOLD = Color.parseColor("#D4A373")
    val GOLD_BRIGHT = Color.parseColor("#E69500")
    val GREEN = Color.parseColor("#3A7D44")
    val BLOOD = Color.parseColor("#E63946")
    val TEXT = Color.parseColor("#F8F9FA")
    val TEXT_DIM = Color.parseColor("#95A597")
    val TEXT_MUTED = Color.parseColor("#5C7060")
}

/** Jungle-themed splash that shows what the app is doing while it connects to the Pi. */
class LoadingView(context: Context) : FrameLayout(context) {
    enum class State { PENDING, ACTIVE, DONE, FAILED }

    var onRetry: (() -> Unit)? = null
    var onOpenTailscale: (() -> Unit)? = null

    val isShowing: Boolean get() = visibility == VISIBLE

    private val handler = Handler(Looper.getMainLooper())
    private val states = Array(STEP_COUNT) { State.PENDING }
    private var loadPercent = 0
    private var seconds = 0

    private val condensedBold = resources.getFont(R.font.barlow_condensed_extrabold)
    private val condensed = resources.getFont(R.font.barlow_condensed_semibold)
    private val body = resources.getFont(R.font.barlow_regular)
    private val bodyMedium = resources.getFont(R.font.barlow_medium)

    private val logo = ImageView(context).apply {
        setImageResource(R.drawable.ic_logo)
        scaleType = ImageView.ScaleType.FIT_CENTER
    }
    private val glow = View(context).apply {
        background = GradientDrawable().apply {
            gradientType = GradientDrawable.RADIAL_GRADIENT
            gradientRadius = dp(100).toFloat()
            colors = intArrayOf(Color.parseColor("#40E69500"), Color.parseColor("#00E69500"))
        }
    }
    private val icons = Array(STEP_COUNT) { StepIcon(context) }
    private val titles = Array(STEP_COUNT) { label(17f, Palette.TEXT, condensed) }
    private val subtitles = Array(STEP_COUNT) { label(13f, Palette.TEXT_DIM, body) }
    private val bar = ProgressBarView(context)
    private val footer = label(13f, Palette.TEXT_MUTED, body, Gravity.CENTER)
    private val progressGroup = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
    private val errorGroup = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        visibility = GONE
    }
    private val errorTitle = label(22f, Palette.BLOOD, condensedBold, Gravity.CENTER)
    private val errorMessage = label(14f, Palette.TEXT_DIM, body, Gravity.CENTER)

    private val pulses = listOf(
        ObjectAnimator.ofPropertyValuesHolder(
            logo,
            android.animation.PropertyValuesHolder.ofFloat(SCALE_X, 1f, 1.05f),
            android.animation.PropertyValuesHolder.ofFloat(SCALE_Y, 1f, 1.05f),
        ),
        ObjectAnimator.ofFloat(glow, ALPHA, 0.55f, 1f),
    ).onEach {
        it.duration = 1400
        it.repeatCount = ValueAnimator.INFINITE
        it.repeatMode = ValueAnimator.REVERSE
        it.interpolator = DecelerateInterpolator()
    }

    private val ticker = object : Runnable {
        override fun run() {
            seconds++
            footer.text = if (seconds >= SLOW_AFTER_SECONDS) {
                context.getString(R.string.footer_slow, seconds)
            } else {
                context.getString(R.string.footer_time, seconds)
            }
            handler.postDelayed(this, 1000)
        }
    }

    init {
        setBackgroundColor(Palette.BACKGROUND)
        isClickable = true

        val logoBox = FrameLayout(context).apply {
            addView(glow, LayoutParams(dp(200), dp(200), Gravity.CENTER))
            addView(logo, LayoutParams(dp(128), dp(128), Gravity.CENTER))
        }

        val wordmark = label(44f, Palette.GOLD_BRIGHT, condensedBold, Gravity.CENTER).apply {
            letterSpacing = 0.02f
            text = SpannableString("GORILLASTATS").apply {
                setSpan(ForegroundColorSpan(Palette.GOLD), 7, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        val tagline = label(14f, Palette.TEXT_DIM, bodyMedium, Gravity.CENTER).apply {
            setText(R.string.tagline)
            letterSpacing = 0.12f
        }

        val card = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(8), dp(20), dp(8))
            background = rounded(Palette.CARD, dp(16), Palette.BORDER)
        }
        val stepTitles = intArrayOf(R.string.step_vpn_title, R.string.step_pi_title, R.string.step_app_title)
        for (i in 0 until STEP_COUNT) {
            titles[i].setText(stepTitles[i])
            val texts = LinearLayout(context).apply {
                orientation = LinearLayout.VERTICAL
                addView(titles[i])
                addView(subtitles[i], LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(2) })
            }
            val row = LinearLayout(context).apply {
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(14), 0, dp(14))
                addView(icons[i], LinearLayout.LayoutParams(dp(28), dp(28)).apply { marginEnd = dp(16) })
                addView(texts, LinearLayout.LayoutParams(0, WRAP, 1f))
            }
            card.addView(row)
            if (i < STEP_COUNT - 1) card.addView(divider(), LinearLayout.LayoutParams(MATCH, 1))
        }

        progressGroup.addView(bar, LinearLayout.LayoutParams(MATCH, dp(6)))
        progressGroup.addView(footer, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(14) })

        errorGroup.addView(errorTitle)
        errorGroup.addView(errorMessage, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(8) })
        errorGroup.addView(
            button(R.string.retry, filled = true) { onRetry?.invoke() },
            LinearLayout.LayoutParams(MATCH, dp(52)).apply { topMargin = dp(20) },
        )
        errorGroup.addView(
            button(R.string.open_tailscale, filled = false) { onOpenTailscale?.invoke() },
            LinearLayout.LayoutParams(MATCH, dp(52)).apply { topMargin = dp(10) },
        )

        val content = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(28), dp(24), dp(28), dp(24))
            addView(logoBox, LinearLayout.LayoutParams(dp(260), dp(200)))
            addView(wordmark, LinearLayout.LayoutParams(MATCH, WRAP))
            addView(tagline, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(4) })
            addView(card, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(32) })
            addView(progressGroup, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(24) })
            addView(errorGroup, LinearLayout.LayoutParams(MATCH, WRAP).apply { topMargin = dp(24) })
        }
        addView(
            ScrollView(context).apply {
                isFillViewport = true
                overScrollMode = OVER_SCROLL_NEVER
                addView(content, ViewGroup.LayoutParams(MATCH, MATCH))
            },
            LayoutParams(MATCH, MATCH),
        )
        reset()
    }

    /** Shows the splash again from the first step. */
    fun reset() {
        animate().cancel()
        handler.removeCallbacksAndMessages(null)
        alpha = 1f
        visibility = VISIBLE
        loadPercent = 0
        seconds = 0
        for (i in 0 until STEP_COUNT) states[i] = State.PENDING
        for (i in 0 until STEP_COUNT) render(i, subtitleFor(i))
        bar.jumpTo(0f)
        footer.text = context.getString(R.string.footer_time, 0)
        errorGroup.visibility = GONE
        progressGroup.visibility = VISIBLE
        handler.postDelayed(ticker, 1000)
        startPulse()
    }

    fun setStep(index: Int, state: State, subtitle: String? = null) {
        states[index] = state
        render(index, subtitle ?: subtitleFor(index))
        updateProgress()
    }

    fun setLoadPercent(percent: Int) {
        loadPercent = percent.coerceIn(0, 100)
        if (states[APP_STEP] == State.ACTIVE) {
            subtitles[APP_STEP].text = context.getString(R.string.step_app_active, loadPercent)
            updateProgress()
        }
    }

    fun showError(title: Int, message: Int) {
        handler.removeCallbacksAndMessages(null)
        stopPulse()
        errorTitle.setText(title)
        errorMessage.setText(message)
        progressGroup.visibility = GONE
        errorGroup.visibility = VISIBLE
    }

    /** Marks everything done and fades the splash out. */
    fun complete() {
        handler.removeCallbacksAndMessages(null)
        for (i in 0 until STEP_COUNT) setStep(i, State.DONE)
        bar.animateTo(1f)
        handler.postDelayed({
            animate().alpha(0f).setDuration(350).withEndAction {
                visibility = GONE
                stopPulse()
            }
        }, 450)
    }

    override fun onDetachedFromWindow() {
        handler.removeCallbacksAndMessages(null)
        stopPulse()
        super.onDetachedFromWindow()
    }

    private fun render(index: Int, subtitle: String) {
        icons[index].state = states[index]
        subtitles[index].text = subtitle
        subtitles[index].setTextColor(
            when (states[index]) {
                State.FAILED -> Palette.BLOOD
                State.DONE -> Palette.GREEN
                else -> Palette.TEXT_DIM
            }
        )
        titles[index].alpha = if (states[index] == State.PENDING) 0.45f else 1f
    }

    private fun subtitleFor(index: Int): String {
        if (index == APP_STEP && states[index] == State.ACTIVE) {
            return context.getString(R.string.step_app_active, loadPercent)
        }
        val id = when (index) {
            0 -> when (states[0]) {
                State.PENDING -> R.string.step_pending
                State.ACTIVE -> R.string.step_vpn_active
                State.DONE -> R.string.step_vpn_done
                State.FAILED -> R.string.step_vpn_failed
            }
            1 -> when (states[1]) {
                State.PENDING -> R.string.step_pending
                State.ACTIVE -> R.string.step_pi_active
                State.DONE -> R.string.step_pi_done
                State.FAILED -> R.string.step_pi_failed
            }
            else -> when (states[2]) {
                State.PENDING, State.ACTIVE -> R.string.step_pending
                State.DONE -> R.string.step_app_done
                State.FAILED -> R.string.step_app_failed
            }
        }
        return context.getString(id)
    }

    private fun updateProgress() {
        var total = 0f
        for (i in 0 until STEP_COUNT) {
            total += when (states[i]) {
                State.DONE -> 1f
                State.ACTIVE -> if (i == APP_STEP) loadPercent / 100f else 0.15f
                else -> 0f
            }
        }
        bar.animateTo(total / STEP_COUNT)
    }

    private fun startPulse() = pulses.forEach { if (!it.isRunning) it.start() }

    private fun stopPulse() {
        pulses.forEach { it.cancel() }
        logo.scaleX = 1f
        logo.scaleY = 1f
        glow.alpha = 1f
    }

    private fun label(sizeSp: Float, color: Int, font: Typeface, gravity: Int = Gravity.START) =
        TextView(context).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
            setTextColor(color)
            typeface = font
            this.gravity = gravity
            includeFontPadding = false
        }

    private fun divider() = View(context).apply { setBackgroundColor(Palette.BORDER) }

    private fun rounded(fill: Int, radius: Int, stroke: Int? = null) = GradientDrawable().apply {
        setColor(fill)
        cornerRadius = radius.toFloat()
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private fun button(text: Int, filled: Boolean, onClick: () -> Unit) = Button(context).apply {
        setText(text)
        isAllCaps = false
        typeface = condensedBold
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
        setTextColor(if (filled) Palette.BACKGROUND else Palette.GOLD)
        stateListAnimator = null
        val shape = if (filled) rounded(Palette.GOLD_BRIGHT, dp(12)) else rounded(Color.TRANSPARENT, dp(12), Palette.BORDER_LIGHT)
        background = RippleDrawable(ColorStateList.valueOf(Color.parseColor("#33FFFFFF")), shape, null)
        setOnClickListener { onClick() }
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()

    private companion object {
        const val STEP_COUNT = 3
        const val APP_STEP = 2
        const val SLOW_AFTER_SECONDS = 10
        const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        const val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT
    }
}

private class StepIcon(context: Context) : View(context) {
    var state = LoadingView.State.PENDING
        set(value) {
            field = value
            updateSpinner()
            invalidate()
        }

    private var angle = 0f
    private val stroke = 2f * resources.displayMetrics.density
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        strokeWidth = stroke
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val spinner = ValueAnimator.ofFloat(0f, 360f).apply {
        duration = 900
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener {
            angle = it.animatedValue as Float
            invalidate()
        }
    }

    private fun updateSpinner() {
        if (state == LoadingView.State.ACTIVE && isAttachedToWindow) {
            if (!spinner.isRunning) spinner.start()
        } else {
            spinner.cancel()
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        updateSpinner()
    }

    override fun onDetachedFromWindow() {
        spinner.cancel()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val r = min(width, height) / 2f - stroke
        when (state) {
            LoadingView.State.PENDING -> {
                paint.style = Paint.Style.STROKE
                paint.color = Palette.BORDER_LIGHT
                canvas.drawCircle(cx, cy, r, paint)
            }
            LoadingView.State.ACTIVE -> {
                paint.style = Paint.Style.STROKE
                paint.color = Palette.BORDER
                canvas.drawCircle(cx, cy, r, paint)
                paint.color = Palette.GOLD_BRIGHT
                canvas.drawArc(RectF(cx - r, cy - r, cx + r, cy + r), angle, 100f, false, paint)
            }
            LoadingView.State.DONE -> {
                paint.style = Paint.Style.FILL
                paint.color = Palette.GREEN
                canvas.drawCircle(cx, cy, r + stroke / 2, paint)
                paint.style = Paint.Style.STROKE
                paint.color = Color.WHITE
                val check = Path().apply {
                    moveTo(cx - r * 0.42f, cy + r * 0.02f)
                    lineTo(cx - r * 0.1f, cy + r * 0.36f)
                    lineTo(cx + r * 0.46f, cy - r * 0.3f)
                }
                canvas.drawPath(check, paint)
            }
            LoadingView.State.FAILED -> {
                paint.style = Paint.Style.FILL
                paint.color = Palette.BLOOD
                canvas.drawCircle(cx, cy, r + stroke / 2, paint)
                paint.style = Paint.Style.STROKE
                paint.color = Color.WHITE
                val d = r * 0.36f
                canvas.drawLine(cx - d, cy - d, cx + d, cy + d, paint)
                canvas.drawLine(cx + d, cy - d, cx - d, cy + d, paint)
            }
        }
    }
}

private class ProgressBarView(context: Context) : View(context) {
    private var fraction = 0f
    private var animator: ValueAnimator? = null
    private val track = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Palette.BORDER }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rect = RectF()

    fun jumpTo(value: Float) {
        animator?.cancel()
        fraction = value
        invalidate()
    }

    fun animateTo(target: Float) {
        animator?.cancel()
        animator = ValueAnimator.ofFloat(fraction, target).apply {
            duration = 450
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                fraction = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        fill.shader = LinearGradient(0f, 0f, w.toFloat(), 0f, Palette.GREEN, Palette.GOLD_BRIGHT, Shader.TileMode.CLAMP)
    }

    override fun onDraw(canvas: Canvas) {
        val radius = height / 2f
        rect.set(0f, 0f, width.toFloat(), height.toFloat())
        canvas.drawRoundRect(rect, radius, radius, track)
        if (fraction > 0f) {
            rect.set(0f, 0f, maxOf(height.toFloat(), width * fraction), height.toFloat())
            canvas.drawRoundRect(rect, radius, radius, fill)
        }
    }
}
