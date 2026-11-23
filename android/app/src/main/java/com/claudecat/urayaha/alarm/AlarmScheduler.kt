package com.claudecat.urayaha.alarm

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * AlarmManager への予約だけをやる殻。「次はいつ鳴るか」は一切計算せず、
 * alarm.ura の "フゥン" コマンドが返す Unix 秒をそのまま登録するだけ。
 */
object AlarmScheduler {
    private const val REQUEST_CODE = 1001
    private const val FLAGS = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE

    fun scheduleAt(context: Context, epochSeconds: Long) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val fireIntent = Intent(context, AlarmReceiver::class.java)
        val firePendingIntent = PendingIntent.getBroadcast(context, REQUEST_CODE, fireIntent, FLAGS)
        val showIntent = PendingIntent.getActivity(
            context, REQUEST_CODE, Intent(context, MainActivity::class.java), FLAGS
        )
        alarmManager.setAlarmClock(
            AlarmManager.AlarmClockInfo(epochSeconds * 1000L, showIntent),
            firePendingIntent
        )
    }

    fun canScheduleExactAlarms(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            return alarmManager.canScheduleExactAlarms()
        }
        return true
    }

    /**
     * bridge の "フゥン" を呼んで次の Unix 秒を得て、そのまま AlarmManager に
     * 登録する。「次はいつか」の判断は .ura 側。ここは受け取った値を渡すだけ。
     * 未設定なら null を返し、何も予約しない。
     */
    fun rescheduleFromBridge(context: Context): Long? {
        val output = UraBridge.run(context, listOf("フゥン")).trim()
        val epoch = output.toLongOrNull() ?: return null
        scheduleAt(context, epoch)
        return epoch
    }
}
