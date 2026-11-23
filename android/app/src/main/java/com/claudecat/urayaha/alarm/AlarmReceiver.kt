package com.claudecat.urayaha.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * AlarmManager が発火させる殻。BroadcastReceiver からの直接の startActivity は
 * Android 10+ で弾かれるため、"イヤッハー" はここでは呼ばない。代わりに
 * フルスクリーンインテント通知を出して RingActivity を前面に呼び出し、
 * そこから先で alarm.ura に委ねる(RingActivity 参照)。ここでやるのは通知を
 * 出すことと、"フゥン" で翌回の Unix 秒を取り直して再予約することだけ。
 */
class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pendingResult = goAsync()
        Thread {
            try {
                UraBridge.init(context)
                AlarmNotifier.notifyRing(context)
                AlarmScheduler.rescheduleFromBridge(context)
            } finally {
                pendingResult.finish()
            }
        }.start()
    }
}
