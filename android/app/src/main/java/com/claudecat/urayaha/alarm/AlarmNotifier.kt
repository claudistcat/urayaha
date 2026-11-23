package com.claudecat.urayaha.alarm

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat

/**
 * 発火時のフルスクリーンインテント通知を組み立てるだけの殻。BroadcastReceiver
 * からの直接の startActivity は Android 10+ でブロックされるため、代わりに
 * この通知で RingActivity を前面に呼び出す(そこから先の "イヤッハー" 呼び出し
 * が本体の判断)。「今回は何を再生するか」はここでは一切決めない。
 */
object AlarmNotifier {
    private const val CHANNEL_ID = "alarm_ring"
    const val NOTIFICATION_ID = 2001
    private const val REQUEST_CODE = 2002

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                CHANNEL_ID,
                context.getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_HIGH
            )
            manager.createNotificationChannel(channel)
        }
    }

    fun notifyRing(context: Context) {
        ensureChannel(context)

        val fullScreenIntent = Intent(context, RingActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pendingIntent = PendingIntent.getActivity(
            context, REQUEST_CODE, fullScreenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle(context.getString(R.string.app_name))
            .setContentText(context.getString(R.string.ring_notification_text))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setContentIntent(pendingIntent)
            .setFullScreenIntent(pendingIntent, true)
            .setAutoCancel(true)
            .build()

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        }
    }

    fun cancel(context: Context) {
        NotificationManagerCompat.from(context).cancel(NOTIFICATION_ID)
    }
}
