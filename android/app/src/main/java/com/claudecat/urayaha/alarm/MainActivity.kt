package com.claudecat.urayaha.alarm

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.provider.Settings
import android.webkit.MimeTypeMap
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.claudecat.urayaha.alarm.databinding.ActivityMainBinding
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 画面・SAF での再生対象(動画/音声)選択・AlarmManager への予約だけをやる殻。
 *
 * 「次は何時に鳴るか」「今回は何を再生するか」「設定の読み書き」は一切
 * ここに書かない。bridge 経由で alarm.ura の "ヤハ"/"フゥン" を呼ぶだけ。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var selectedSourcePath: String? = null

    private val pickSource =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            if (uri != null) copyPickedFileToFilesDir(uri)
        }

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        UraBridge.init(this)
        UraBridge.syncScript(this)

        binding.timePicker.setIs24HourView(true)

        binding.buttonChooseVideo.setOnClickListener {
            pickSource.launch(arrayOf("audio/*", "video/*"))
        }
        binding.buttonSave.setOnClickListener { onSaveClicked() }

        maybeRequestExactAlarmPermission()
        maybeRequestNotificationPermission()
        refreshNextAlarmLabel()
    }

    override fun onResume() {
        super.onResume()
        refreshNextAlarmLabel()
    }

    /**
     * 拡張子を保ってコピーする。IntentOpener は .ura から返ってきたパスの拡張子
     * だけを手がかりに開く Intent の type を決めるため(alarm.json には拡張子や
     * MIME タイプを持たせない。.ura にとっては中身が動画か音声かは関知しない
     * 対象のパスでしかない、ADR-0005)。
     */
    private fun copyPickedFileToFilesDir(uri: Uri) {
        val mediaDir = File(filesDir, "media").apply { mkdirs() }
        mediaDir.listFiles()?.forEach { it.delete() }
        val extension = resolveExtension(uri)
        val fileName = if (extension != null) "alarm_source.$extension" else "alarm_source"
        val target = File(mediaDir, fileName)
        contentResolver.openInputStream(uri)?.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        }
        selectedSourcePath = target.absolutePath
        binding.textVideoPath.text = target.name
    }

    private fun resolveExtension(uri: Uri): String? {
        val displayName = contentResolver.query(
            uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null
        )?.use { cursor -> if (cursor.moveToFirst()) cursor.getString(0) else null }
        val fromName = displayName?.substringAfterLast('.', missingDelimiterValue = "")
            ?.takeIf { it.isNotEmpty() }
        if (fromName != null) return fromName
        val mimeType = contentResolver.getType(uri) ?: return null
        return MimeTypeMap.getSingleton().getExtensionFromMimeType(mimeType)
    }

    private fun onSaveClicked() {
        val sourcePath = selectedSourcePath
        if (sourcePath == null) {
            Toast.makeText(this, R.string.no_video_selected, Toast.LENGTH_SHORT).show()
            return
        }
        val hour = binding.timePicker.hour
        val minute = binding.timePicker.minute
        val timeText = String.format(Locale.ROOT, "%02d:%02d", hour, minute)

        Thread {
            val result = UraBridge.run(this, listOf("ヤハ", timeText, sourcePath)).trim()
            runOnUiThread {
                if (result.startsWith("OK")) {
                    scheduleFromBridgeAsync()
                } else {
                    Toast.makeText(this, result, Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun scheduleFromBridgeAsync() {
        Thread {
            val epoch = AlarmScheduler.rescheduleFromBridge(this)
            runOnUiThread { showNextAlarm(epoch) }
        }.start()
    }

    private fun refreshNextAlarmLabel() {
        Thread {
            val output = UraBridge.run(this, listOf("フゥン")).trim()
            val epoch = output.toLongOrNull()
            runOnUiThread { showNextAlarm(epoch) }
        }.start()
    }

    private fun showNextAlarm(epochSeconds: Long?) {
        binding.textNextAlarm.text = if (epochSeconds == null) {
            getString(R.string.no_alarm_set)
        } else {
            val formatted = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
                .format(Date(epochSeconds * 1000L))
            getString(R.string.next_alarm_prefix) + formatted
        }
    }

    private fun maybeRequestExactAlarmPermission() {
        if (Build.VERSION.SDK_INT in Build.VERSION_CODES.S..Build.VERSION_CODES.S_V2) {
            if (!AlarmScheduler.canScheduleExactAlarms(this)) {
                Toast.makeText(this, R.string.exact_alarm_permission_title, Toast.LENGTH_LONG).show()
                startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM))
            }
        }
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }
}
