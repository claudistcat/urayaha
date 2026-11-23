package com.claudecat.urayaha.alarm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * 端末再起動後、既存の設定があれば再予約するだけの殻。「次はいつか」は
 * alarm.ura の "フゥン" が計算する(AlarmScheduler.rescheduleFromBridge 経由)。
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val pendingResult = goAsync()
        Thread {
            try {
                UraBridge.init(context)
                UraBridge.syncScript(context)
                AlarmScheduler.rescheduleFromBridge(context)
            } finally {
                pendingResult.finish()
            }
        }.start()
    }
}
