package com.claudecat.urayaha.alarm

import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import com.claudecat.urayaha.alarm.databinding.ActivityRingBinding

/**
 * フルスクリーンインテント通知から前面に出るだけの殻。「今回は何を再生するか」
 * は判断せず、bridge の "イヤッハー" を alarm.ura にそのまま委ねる。前面
 * (RESUMED)から呼ぶことで、そこから先の startActivity が許可される。
 */
class RingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRingBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOverLockScreen()
        binding = ActivityRingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.buttonClose.setOnClickListener { finish() }

        UraBridge.init(this)
        UraBridge.registerOpener(this, IntentOpener(this))
        Thread {
            UraBridge.run(this, listOf("イヤッハー"))
            runOnUiThread { AlarmNotifier.cancel(this) }
        }.start()
    }

    private fun showOverLockScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD or
                    WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
            )
        }
    }
}
