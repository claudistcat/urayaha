package com.claudecat.urayaha.alarm

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import java.io.File

/**
 * bridge.py の set_opener() に渡す実装。「これを開いて」という alarm.ura の
 * 意図(ADR-0005)を、Android の Intent(ACTION_VIEW) に翻訳するだけ。対象が
 * 動画か音声か・どれを選ぶかはここでは判断しない(判断済みの対象を受け取り、
 * 拡張子から MIME タイプを引くだけ)。
 *
 * 呼び出し元は RingActivity(前面/RESUMED 状態)に限る。実機(Android 13)で
 * 確認済みのとおり、BroadcastReceiver から直接この startActivity を呼ぶと
 * Background activity start としてブロックされる。
 */
class IntentOpener(private val context: Context) : Opener {
    override fun open(target: String) {
        val intent = if (target.startsWith("http://") || target.startsWith("https://")) {
            Intent(Intent.ACTION_VIEW, Uri.parse(target))
        } else {
            val uri = FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", File(target)
            )
            Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, resolveMimeType(target))
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    private fun resolveMimeType(target: String): String {
        val extension = target.substringAfterLast('.', missingDelimiterValue = "").lowercase()
        if (extension.isEmpty()) return "*/*"
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension) ?: "*/*"
    }
}
