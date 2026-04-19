package com.example.eyecare

import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.View
import android.view.WindowManager

/**
 * 这是一个 Android 后台护眼服务的基础实现（核心代码）
 * 作用：在整个手机屏幕上层叠加一层半透明的黄色遮罩，实现过滤蓝光的效果。
 */
class EyeCareService : Service() {

    private lateinit var windowManager: WindowManager
    private lateinit var overlayView: View

    // onBind 在这个场景不需要，因为我们是作为一个后台运行的 Service
    override fun onBind(intent: Intent?): IBinder? {
        return null 
    }

    override fun onCreate() {
        super.onCreate()
        // 获取系统的窗口管理器
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager

        // 创建一个无边框的 View，用作滤镜
        overlayView = View(this).apply {
            // #40FFCC00 表示带有 25% 不透明度的黄色 (护眼暖色调)
            setBackgroundColor(Color.parseColor("#40FFCC00")) 
        }

        // 配置悬浮窗的核心参数 (决定它如何显示在最上层)
        val layoutParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT, // 铺满全屏
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY // Android 8.0 及以上要求使用这个类型
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_SYSTEM_OVERLAY // 兼容 Android老版本
            },
            // 这些 FLAG 极其重要：
            // FLAG_NOT_TOUCHABLE: 让用户的触摸操作事件穿透这个遮罩，点到下层的 App
            // FLAG_NOT_FOCUSABLE: 不要拦截输入焦点
            // FLAG_LAYOUT_IN_SCREEN: 允许遮罩覆盖到状态栏
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT // 支持透明度
        )

        // 将遮罩正式添加到屏幕上
        windowManager.addView(overlayView, layoutParams)
    }

    override fun onDestroy() {
        super.onDestroy()
        // 当关闭护眼模式时，移除遮罩，避免内存泄漏
        if (::overlayView.isInitialized) {
            windowManager.removeView(overlayView)
        }
    }
}
